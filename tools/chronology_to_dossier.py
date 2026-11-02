#!/usr/bin/env python3
"""Offline bridge: sourced chronology + author causal links -> Narrative Impact v1."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from manuscript_pipeline import ProjectError


def by_id(items, label):
    if not isinstance(items, list):
        raise ProjectError(label + " must be an array")
    result = {}
    for obj in items:
        if not isinstance(obj, dict) or not isinstance(obj.get("id"), str) or not obj["id"]:
            raise ProjectError(label + " requires nonempty IDs")
        if obj["id"] in result:
            raise ProjectError("Duplicate " + label + ": " + obj["id"])
        result[obj["id"]] = obj
    return result


def convert(chronology, relations, revised=None, overrides=None):
    if not isinstance(chronology, dict) or chronology.get("schema_version") != 1:
        raise ProjectError("Expected chronology schema_version 1")
    if not isinstance(relations, dict) or relations.get("format_version") != 1:
        raise ProjectError("Expected relations format_version 1")
    if revised is not None and (not isinstance(revised, dict) or revised.get("schema_version") != 1):
        raise ProjectError("Revised chronology must have schema_version 1")
    old = by_id(chronology.get("events"), "events")
    new = by_id(revised.get("events"), "revised events") if revised else old
    manual = by_id(relations.get("manual_facts", []), "manual facts")
    rules = by_id(relations.get("rules"), "rules")
    if not rules:
        raise ProjectError("At least one causal rule required")
    if (set(old) | set(new) | set(manual)) & set(rules) or set(manual) & (set(old) | set(new)):
        raise ProjectError("Conflicting fact and rule IDs")
    overrides = overrides if overrides is not None else {}
    if not isinstance(overrides, dict) or set(overrides) - (set(old) | set(new) | set(manual)):
        raise ProjectError("Overrides must target known fact IDs")
    if any(value not in ("present", "absent") for value in overrides.values()):
        raise ProjectError("Override values must be present or absent")
    facts = []
    for key in dict.fromkeys([*old, *new]):
        src = old.get(key) or new[key]
        if not isinstance(src.get("description"), str) or not src["description"]:
            raise ProjectError("Missing event description: " + key)
        facts.append({
            "id": key, "label": src["description"],
            "before": "present" if key in old else "absent",
            "after": overrides.get(key, "present" if key in new else "absent"),
            "evidence": src.get("evidence", {}),
        })
    for key, fact in manual.items():
        if not isinstance(fact.get("label"), str) or not fact["label"] or not isinstance(fact.get("evidence"), dict):
            raise ProjectError("Manual fact requires label and evidence: " + key)
        facts.append({"id": key, "label": fact["label"], "before": "present",
                      "after": overrides.get(key, "present"), "evidence": fact["evidence"]})
    ids = {x["id"] for x in facts}
    output_rules = []
    for key, rule in rules.items():
        paths = rule.get("because_any")
        if not isinstance(paths, list) or not paths or any(not isinstance(p, list) or not p for p in paths):
            raise ProjectError("Invalid because_any: " + key)
        groups = []
        for path in paths:
            group = []
            for token in path:
                if not isinstance(token, str) or not token:
                    raise ProjectError("Invalid dependency")
                if token.startswith("rule:"):
                    target = token[5:]
                    if target not in rules:
                        raise ProjectError("Unknown upstream rule: " + token)
                    group.append({"rule": target})
                else:
                    if token not in ids:
                        raise ProjectError("Unknown upstream fact: " + token)
                    group.append({"fact": token, "equals": "present"})
            groups.append(group)
        terms = rule.get("evidence_terms", [])
        if not isinstance(terms, list) or any(not isinstance(t, str) or len(t) < 3 for t in terms):
            raise ProjectError("Invalid evidence_terms: " + key)
        output_rules.append({"id": key, "label": rule.get("label", key),
                             "because_any": groups, "evidence_terms": terms,
                             "review_note": rule.get("review_note", "")})
    aliases = relations.get("aliases", [])
    if not isinstance(aliases, list) or any(not isinstance(s, str) for s in aliases):
        raise ProjectError("Invalid aliases")
    result = {"format_version": 1, "aliases": aliases,
              "facts": facts, "rules": output_rules,
              "provenance": {
                  "source_commit": chronology.get("source_commit"),
                  "revised_source_commit": revised.get("source_commit") if revised else None,
                  "baseline": revised is None and not overrides,
                  "note": "Unchanged event IDs are presumed equivalent, not semantically verified. "
                          "Author review needed on new manuscript versions.",
              }}
    from narrative_impact import dossier, evaluate
    checked = dossier(result)
    evaluate(checked, "before")
    evaluate(checked, "after")  # Also detects cycles.
    return result


def cli(argv=None):
    parser = argparse.ArgumentParser(description="Local chronology -> Narrative Impact dossier v1")
    parser.add_argument("chronology", type=Path)
    parser.add_argument("relations", type=Path)
    parser.add_argument("--revised", type=Path)
    parser.add_argument("--overrides", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    try:
        source_paths = [p.resolve() for p in
                        [args.chronology, args.relations, args.revised, args.overrides] if p]
        output = args.out.resolve()
        if output in source_paths or (output.exists() and (not args.force or not output.is_file())):
            raise ProjectError("Refusing to overwrite inputs or report without --force")
        def load(p):
            return json.loads(p.read_text(encoding="utf-8")) if p else None
        result = convert(load(args.chronology), load(args.relations),
                         load(args.revised), load(args.overrides))
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Converted {len(result['facts'])} facts and {len(result['rules'])} causal rules")
        return 0
    except (OSError, UnicodeError, ValueError) as exc:
        print("Conversion error: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(cli())
