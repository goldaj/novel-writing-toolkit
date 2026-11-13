"""Review workflow: stable finding identifiers, evidence fingerprints, decisions.

Decisions never suppress an issue. A changed finding invalidates its previous
review status until the author has examined the new evidence.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from manuscript_pipeline import ProjectError, read_utf8

STATUSES = {"open", "confirmed", "intentional", "false_positive", "needs_rewrite"}
MAX_DECISIONS = 10000
MAX_NOTE_LENGTH = 2000


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def identity(kind: str, finding: dict) -> str:
    if kind == "consequence":
        return "consequence:" + str(finding["event"])
    # These fields identify the issue regardless of prose or reworded details.
    keys = ("code", "event", "item", "character", "fact", "chapter", "facts",
            "subject", "attribute")
    locator = {key: finding[key] for key in keys if key in finding}
    return "issue:" + hashlib.sha256(canonical(locator).encode("utf-8")).hexdigest()[:24]


def fingerprint(finding: dict) -> str:
    # Ignore UI/reviewer metadata to keep the fingerprint a property of evidence.
    material = {k: v for k, v in finding.items()
                if k not in {"review", "review_id", "fingerprint"}}
    return hashlib.sha256(canonical(material).encode("utf-8")).hexdigest()


def read_decisions(path: Path) -> dict:
    try:
        raw = json.loads(read_utf8(path))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ProjectError("Cannot read review decisions: " + str(exc)) from exc
    if not isinstance(raw, dict) or raw.get("format_version") != 1:
        raise ProjectError("Expected review decisions format_version 1")
    values = raw.get("items", [])
    if not isinstance(values, list) or len(values) > MAX_DECISIONS:
        raise ProjectError("Review decisions must be a bounded array")
    seen = set()
    result = {}
    for item in values:
        if not isinstance(item, dict) or set(item) - {"id", "fingerprint", "status", "note"}:
            raise ProjectError("Malformed review item")
        ident = item.get("id")
        if not isinstance(ident, str) or not (ident.startswith("issue:") or
                                              ident.startswith("consequence:")):
            raise ProjectError("Invalid review ID")
        if ident in seen:
            raise ProjectError("Duplicate review ID: " + ident)
        seen.add(ident)
        sha = item.get("fingerprint")
        if not isinstance(sha, str) or len(sha) != 64 or any(
                ch not in "0123456789abcdef" for ch in sha):
            raise ProjectError("Review fingerprint must be lowercase SHA-256")
        status = item.get("status")
        if status not in STATUSES:
            raise ProjectError("Unknown review status: " + str(status))
        note = item.get("note", "")
        if not isinstance(note, str) or len(note) > MAX_NOTE_LENGTH:
            raise ProjectError("Review note must be text of at most 2000 characters")
        result[ident] = {"id": ident, "fingerprint": sha, "status": status, "note": note}
    return result


def attach(report: dict, decisions: dict | None = None) -> dict:
    """Mutate an already-validated report with traceable author review states."""
    decisions = decisions or {}
    current = report["after"] if report["kind"] == "narrative_comparison" else report
    findings = [("issue", x) for x in current["issues"]]
    if report["kind"] == "narrative_comparison":
        findings.extend(("consequence", x) for x in report["consequences"])
    attached = set()
    summary = {"open": 0, "confirmed": 0, "intentional": 0,
               "false_positive": 0, "needs_rewrite": 0, "stale": 0}
    for kind, finding in findings:
        ident = identity(kind, finding)
        if ident in attached:
            raise ProjectError("Findings have conflicting review IDs: " + ident)
        attached.add(ident)
        expected = fingerprint(finding)
        saved = decisions.get(ident)
        stale = bool(saved and saved["fingerprint"] != expected)
        status = saved["status"] if saved and not stale else "open"
        note = saved["note"] if saved and not stale else ""
        finding["review"] = {"id": ident, "fingerprint": expected,
                             "status": status, "note": note, "stale": stale}
        summary[status] += 1
        if stale:
            summary["stale"] += 1
    report["review_summary"] = summary
    report["review_warnings"] = [{
        "id": ident, "reason": "previous finding no longer exists"
    } for ident in decisions if ident not in attached]
    return report
