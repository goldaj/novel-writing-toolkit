#!/usr/bin/env python3
"""Conservative import of a legacy event/knowledge notebook into narrative v1.

Local only; chronology, character knowledge and causal links are NOT invented.
No private book content is embedded or transmitted by this tool.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

from manuscript_pipeline import ProjectError, load_project, read_utf8
from narrative_memory import validate


def load_json(path: Path) -> dict:
    try:
        obj = json.loads(read_utf8(path))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ProjectError("Cannot load legacy file: " + str(exc)) from exc
    if not isinstance(obj, dict):
        raise ProjectError("Legacy document must be an object")
    return obj


def key_for(prefix: str, value: str) -> str:
    return prefix + hashlib.sha256(value.casefold().encode("utf-8")).hexdigest()[:16]


def evidence_source(evidence: dict, allowed: set[str]) -> dict:
    if not isinstance(evidence, dict):
        raise ProjectError("Missing legacy evidence")
    raw = evidence.get("path")
    quote = evidence.get("needle")
    if not isinstance(raw, str) or not raw or not isinstance(quote, str) or not quote.strip():
        raise ProjectError("Evidence requires a path and an exact needle")
    # Legacy paths can be relative to the repository, rather than project.json.
    # Match a UNIQUE full declared suffix, never look up an arbitrary file.
    normalized = raw.replace("\\", "/").lstrip("./")
    matches = [path for path in allowed if normalized == path or
               normalized.endswith("/" + path)]
    if len(matches) != 1:
        raise ProjectError("Ambiguous or undeclared legacy evidence path: " + raw)
    if len(quote) > 1600:
        raise ProjectError("Evidence needle exceeds the source quote limit")
    return {"chapter": matches[0], "quote": quote}


def convert(project: Path, chronology: dict, knowledge: dict | None = None,
            relations: dict | None = None) -> dict:
    """Convert observable fields only, preserving uninterpreted legacy metadata.

    The legacy sequence is narrative file order, NOT fictional time.
    The knowledge anchor is evidence location, NOT proven acquisition time.
    Causal rules without an explicit effect event remain unmapped metadata.
    """
    if not isinstance(chronology, dict) or chronology.get("schema_version") != 1:
        raise ProjectError("Expected legacy chronology schema_version 1")
    if knowledge is not None and (not isinstance(knowledge, dict) or
                                  knowledge.get("schema_version") != 1):
        raise ProjectError("Expected legacy knowledge schema_version 1")
    if relations is not None and (not isinstance(relations, dict) or
                                  relations.get("format_version") != 1):
        raise ProjectError("Expected legacy relations format_version 1")
    _info, declared = load_project(project.resolve())
    paths = {path.relative_to(project.resolve()).as_posix() for path, _ in declared}
    legacy_events = chronology.get("events")
    if not isinstance(legacy_events, list):
        raise ProjectError("Legacy chronology events must be an array")
    events = []
    seen = set()
    for old in legacy_events:
        if not isinstance(old, dict):
            raise ProjectError("Legacy event must be an object")
        ident, label = old.get("id"), old.get("description")
        if not isinstance(ident, str) or not isinstance(label, str) or not label.strip():
            raise ProjectError("Legacy event requires id and description")
        if ident in seen:
            raise ProjectError("Duplicate legacy event: " + ident)
        seen.add(ident)
        events.append({
            "id": ident, "label": label, "time_index": None, "participants": [],
            "legacy_time_label": old.get("when"),
            "legacy_narrative_sequence": old.get("sequence"),
            "source": evidence_source(old.get("evidence"), paths)
        })
    if not events:
        raise ProjectError("Legacy chronology must contain events")
    characters = []
    char_ids = {}
    facts = []
    fact_ids = set()
    states = []
    entries = knowledge.get("entries", []) if knowledge else []
    if not isinstance(entries, list):
        raise ProjectError("Legacy knowledge entries must be an array")
    for old in entries:
        if not isinstance(old, dict):
            raise ProjectError("Legacy knowledge entry must be an object")
        knower, topic = old.get("knower"), old.get("topic")
        if not isinstance(knower, str) or not knower.strip() or not isinstance(topic, str) or not topic.strip():
            raise ProjectError("Legacy knowledge needs a knower and a topic")
        normalized = knower.casefold()
        if normalized not in char_ids:
            char_ids[normalized] = key_for("C_", knower)
            characters.append({"id": char_ids[normalized], "name": knower,
                               "aliases": [], "role": "reader" if normalized == "lecteur" else "undetermined"})
        topic_id = key_for("T_", topic)
        source = evidence_source(old.get("evidence"), paths)
        if topic_id not in fact_ids:
            fact_ids.add(topic_id)
            facts.append({"id": topic_id, "subject": "world", "attribute": "unverified_topic",
                          "value": topic, "confidence": "tentative", "source": source,
                          "legacy_note": "Topic only, NOT confirmed as an objective world fact"})
        ident = old.get("id")
        if not isinstance(ident, str) or not ident:
            raise ProjectError("Legacy knowledge entry requires ID")
        states.append({"id": ident, "character": char_ids[normalized], "fact": topic_id,
                       "state": "suspects", "source": source,
                       "legacy_status": old.get("status"),
                       "legacy_anchor_event": old.get("anchor_id"),
                       "migration_review": "State and acquisition time require human classification"})

    manual = relations.get("manual_facts", []) if relations else []
    rules = relations.get("rules", []) if relations else []
    if not isinstance(manual, list) or not isinstance(rules, list):
        raise ProjectError("Legacy relations arrays required")
    for item in manual:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise ProjectError("Invalid legacy manual fact")
        facts.append({"id": item["id"], "subject": "world", "attribute": "legacy_canon",
                      "value": "present", "confidence": "tentative",
                      "label": item.get("label"), "source": evidence_source(item.get("evidence"), paths),
                      "migration_review": "Confirm precise world attribute/value and dates"})
    result = {
        "schema_version": 1, "project": chronology.get("title", ""),
        "characters": characters, "events": events, "facts": facts,
        "knowledge": states, "dependencies": [],
        "legacy_unmapped_rules": rules,
        "migration": {
            "source": "legacy chronology/knowledge/relations",
            "time_index_inferred": False,
            "knowledge_states_inferred": False,
            "causal_rules_mapped": 0,
            "causal_rules_require_review": len(rules),
            "notes": [
                "Sequence is narrative order, not proof of fictional chronology.",
                "Knowledge anchor is source evidence, not a certified acquisition event.",
                "Legacy rules without effect_event were preserved, never silently guessed.",
                "All subjects and quoted source passages remain in this LOCAL output."
            ]
        }
    }
    # Ensure the output is acceptable to the actual target engine before writing.
    validate(project, result)
    return result


def cli(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Offline, conservative legacy narrative importer")
    p.add_argument("project", type=Path)
    p.add_argument("chronology", type=Path)
    p.add_argument("--knowledge", type=Path)
    p.add_argument("--relations", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--force", action="store_true")
    args = p.parse_args(argv)
    try:
        inputs = [x.resolve() for x in (args.chronology, args.knowledge, args.relations) if x]
        _info, sections = load_project(args.project.resolve())
        protected = {p.resolve() for p, _ in sections}
        protected.update(inputs)
        protected.add((args.project.resolve() / "project.json").resolve())
        dest = args.out.resolve()
        if dest in protected or dest.is_dir() or (dest.exists() and not args.force):
            raise ProjectError("Refusing to overwrite source or existing output")
        result = convert(args.project, load_json(args.chronology),
                         load_json(args.knowledge) if args.knowledge else None,
                         load_json(args.relations) if args.relations else None)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        temp = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False,
                                             dir=args.out.parent, prefix=".narrative-",
                                             suffix=".tmp") as handle:
                temp = Path(handle.name)
                handle.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
            os.replace(temp, args.out)
        finally:
            if temp is not None and temp.exists():
                temp.unlink()
        print("Converted " + str(len(result["events"])) + " events, " +
              str(len(result["knowledge"])) + " epistemic notes; " +
              str(len(result["legacy_unmapped_rules"])) + " causal rules awaiting review")
        return 0
    except (OSError, UnicodeError, ValueError) as exc:
        print("Legacy import error: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(cli())
