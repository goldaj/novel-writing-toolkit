#!/usr/bin/env python3
"""Human-gated promotion of local AI candidates into Narrative Memory v1.

Never infer a complete structured fact or relationship from the model's prose.
An AUTHOR must supply and explicitly accept each structured annotation.
Input manuscripts, candidate batches, decisions and old memory are immutable.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

from manuscript_pipeline import ProjectError, load_project, read_utf8
from narrative_memory import validate, source_issues
from narrative_local_assist import segments

CATEGORIES = {"event": "events", "fact": "facts",
              "knowledge": "knowledge", "causal_link": "dependencies"}
MAX_CANDIDATES = 20000


def load(path: Path) -> dict:
    try:
        obj = json.loads(read_utf8(path))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ProjectError("Cannot load curation input: " + str(type(exc).__name__)) from exc
    if not isinstance(obj, dict):
        raise ProjectError("Curation input must be an object")
    return obj


def catalog(batch: dict) -> dict:
    if (batch.get("format_version") != 1 or
            batch.get("kind") != "local_narrative_candidates"):
        raise ProjectError("Expected local_narrative_candidates format_version 1")
    records = batch.get("candidates")
    if not isinstance(records, list) or len(records) > MAX_CANDIDATES:
        raise ProjectError("Candidates must be a bounded array")
    out = {}
    for record in records:
        if not isinstance(record, dict) or record.get("kind") not in CATEGORIES:
            raise ProjectError("Malformed candidate")
        ident = record.get("id")
        if not isinstance(ident, str) or not ident.startswith("C_") or len(ident) > 90:
            raise ProjectError("Candidate requires a valid ID")
        if ident in out:
            raise ProjectError("Duplicate candidate ID: " + ident)
        if record.get("status") != "pending_author_review" or record.get("trust") != "hypothesis":
            raise ProjectError("Candidate not marked as unverified")
        source = record.get("source")
        if not isinstance(source, dict):
            raise ProjectError("Candidate needs verifiable provenance")
        if (not isinstance(source.get("chapter"), str) or
                not isinstance(source.get("quote"), str) or
                not source["quote"].strip() or
                not isinstance(source.get("paragraph"), int) or
                type(source.get("slice_index")) is not int or source["slice_index"] < 0 or
                not isinstance(source.get("sha256"), str) or
                len(source["sha256"]) != 64):
            raise ProjectError("Candidate has invalid source metadata")
        out[ident] = record
    return out


def validate_provenance(project: Path, batch: dict, selected: list[dict]) -> None:
    """Reconstruct original blocks and verify exact source hashes and quotations.

    Changing the manuscript or the chunk setting invalidates its old candidates.
    This checks quotation authenticity, not the model's interpretation.
    """
    max_chars = batch.get("max_chars", 2800)
    if type(max_chars) is not int:
        raise ProjectError("Invalid extraction max_chars")
    existing = {
        (part["chapter"], part["paragraph"], part["slice_index"], part["sha256"]):
        part["content"] for part in segments(project, max_chars)
    }
    for candidate in selected:
        src = candidate["source"]
        key = (src["chapter"], src["paragraph"], src["slice_index"], src["sha256"])
        if key not in existing:
            raise ProjectError("Source block changed; rerun extraction for " + candidate["id"])
        norm = lambda x: " ".join(x.split())
        if norm(src["quote"]) not in norm(existing[key]):
            raise ProjectError("Candidate quote not present in its original block: " + candidate["id"])


def decision_items(raw: dict, available: dict) -> tuple[list[tuple[dict, dict]], int]:
    if raw.get("format_version") != 1:
        raise ProjectError("Decisions must use format_version 1")
    items = raw.get("items")
    if not isinstance(items, list) or len(items) > MAX_CANDIDATES:
        raise ProjectError("Decisions must be a bounded array")
    accepted = []
    seen = set()
    skipped = 0
    for item in items:
        if not isinstance(item, dict):
            raise ProjectError("Invalid decision")
        ident, action = item.get("id"), item.get("action")
        if not isinstance(ident, str) or ident not in available:
            raise ProjectError("Decision references unknown candidate")
        if ident in seen:
            raise ProjectError("Duplicate decision for candidate " + ident)
        seen.add(ident)
        if action not in {"accept", "reject", "skip"}:
            raise ProjectError("Decision must be accept, reject or skip")
        if action != "accept":
            if "annotation" in item:
                raise ProjectError("Only accepted decisions may contain annotations")
            skipped += 1
            continue
        annotation = item.get("annotation")
        if not isinstance(annotation, dict) or not annotation:
            raise ProjectError("Acceptance requires a complete author annotation: " + ident)
        if "source" in annotation or "curation" in annotation:
            raise ProjectError("Annotation source and curation provenance are managed by the tool")
        accepted.append((available[ident], copy.deepcopy(annotation)))
    return accepted, skipped


def template(batch: dict) -> dict:
    return {"format_version": 1, "notice": "Every candidate is skipped until an author "
            "explicitly changes action to accept and supplies a full schema-v1 annotation. "
            "Do not submit these decisions as proof of literary truth.",
            "items": [{"id": ident, "action": "skip"} for ident in catalog(batch)]}


def promote(project: Path, baseline: dict, batch: dict, decisions: dict) -> tuple[dict, dict]:
    """Build a NEW memory; all changes are human-authorized and then schema-checked."""
    validate(project, baseline)
    available = catalog(batch)
    selected, skipped = decision_items(decisions, available)
    validate_provenance(project, batch, [candidate for candidate, _ in selected])
    result = copy.deepcopy(baseline)
    for key in CATEGORIES.values():
        result.setdefault(key, [])
    # IDs are unique per category as checked by validate(); cross-category IDs
    # may share names, because references always name their category.
    counts = {kind: 0 for kind in CATEGORIES}
    accepted_ids = []
    for candidate, annotation in selected:
        kind = candidate["kind"]
        annotation["source"] = {
            "chapter": candidate["source"]["chapter"],
            "quote": candidate["source"]["quote"]
        }
        annotation["curation"] = {
            "origin": "human_accepted_local_candidate",
            "candidate_id": candidate["id"],
            "model": str(batch.get("model", ""))[:100],
            "source_sha256": candidate["source"]["sha256"]
        }
        result[CATEGORIES[kind]].append(annotation)
        counts[kind] += 1
        accepted_ids.append(candidate["id"])
    checked = validate(project, result)
    introduced = {"event:" + x["id"] for x in result["events"][len(baseline.get("events", [])) :]}
    introduced |= {"fact:" + x["id"] for x in result["facts"][len(baseline.get("facts", [])) :]}
    introduced |= {"knowledge:" + x["id"] for x in result["knowledge"][len(baseline.get("knowledge", [])) :]}
    introduced |= {"dependency:" + x["id"] for x in result["dependencies"][len(baseline.get("dependencies", [])) :]}
    stale = [issue for issue in checked["issues"] if issue["code"] == "stale_source"
             and issue["item"] in introduced]
    if stale:
        raise ProjectError("Accepted annotation has a stale quote: " + stale[0]["item"])
    log = result.setdefault("curation_history", [])
    if not isinstance(log, list):
        raise ProjectError("curation_history must be an array")
    log.append({
        "action": "author_reviewed_import",
        "accepted_candidate_ids": accepted_ids,
        "accepted_count": len(accepted_ids),
        "model": str(batch.get("model", ""))[:100]
    })
    return result, {"accepted": len(accepted_ids), "skipped": skipped,
                    "accepted_by_kind": counts, "validation_findings": len(checked["issues"])}


def guarded_write(output: Path, payload: dict, protected: list[Path], force: bool) -> None:
    dest = output.resolve()
    if dest in {p.resolve() for p in protected} or dest.is_dir() or (
            dest.exists() and not force):
        raise ProjectError("Refusing to overwrite source or existing output")
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False,
                                         dir=output.parent, prefix=".curation-", suffix=".tmp") as fp:
            temp = Path(fp.name)
            json.dump(payload, fp, ensure_ascii=False, indent=2)
            fp.write("\n")
        os.replace(temp, output)
    finally:
        if temp is not None and temp.exists():
            temp.unlink()


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Human-reviewed, local narrative curation")
    sub = parser.add_subparsers(dest="command", required=True)
    a = sub.add_parser("template", help="Create a default-deny author review sheet")
    a.add_argument("candidates", type=Path)
    b = sub.add_parser("apply", help="Create a NEW validated memory from approved annotations")
    b.add_argument("project", type=Path)
    b.add_argument("memory", type=Path)
    b.add_argument("candidates", type=Path)
    b.add_argument("decisions", type=Path)
    for p in (a, b):
        p.add_argument("--out", type=Path, required=True)
        p.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "template":
            payload = template(load(args.candidates))
            protected = [args.candidates]
            detail = str(len(payload["items"])) + " unapproved suggestions"
        else:
            payload, report = promote(args.project, load(args.memory),
                                      load(args.candidates), load(args.decisions))
            _project_info, sources = load_project(args.project.resolve())
            protected = [args.memory, args.candidates, args.decisions,
                         args.project / "project.json", *(p for p, _ in sources)]
            detail = str(report["accepted"]) + " human-approved annotations, " + (
                str(report["validation_findings"]) + " validation issues to inspect")
        guarded_write(args.out, payload, protected, args.force)
        print("Curation: " + detail)
        return 0
    except (OSError, UnicodeError, ValueError) as exc:
        print("Narrative curation error (" + type(exc).__name__ + ")", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(cli())
