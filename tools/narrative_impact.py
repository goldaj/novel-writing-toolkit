#!/usr/bin/env python3
"""Version-to-version narrative impact review. Evidence, not literary verdicts."""
from __future__ import annotations

import argparse
import difflib
import html
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from manuscript_pipeline import ProjectError, load_project, read_utf8

WORD = re.compile(r"[^\W_]+(?:[’'-][^\W_]+)*", re.UNICODE)
STOP = set("""avec aussi alors après avant beaucoup bien cette comme dans des donc elle elles entre était été être fait faire faut
ils leur leurs mais même moins nous notre pour puis quand que quel quelle quels quelles qui quoi sans sont sous sur
tout tous toute toutes très une vous votre vers cela celui celle chaque cette ces ses son sa de du le la les un au aux
ce cet en et ou par ne pas se il je tu on y a à d l c n j qu s est ont plus si encore car cependant dont""".split())


@dataclass(frozen=True)
class Paragraph:
    chapter: str
    number: int
    line: int
    text: str

    def ref(self) -> dict:
        return {"chapter": self.chapter, "paragraph": self.number, "line": self.line,
                "excerpt": self.text[:420]}


def paragraphs(root: Path) -> tuple[list[Paragraph], list[str]]:
    _, paths = load_project(root.resolve())
    result: list[Paragraph] = []
    chapters: list[str] = []
    for path, heading in paths:
        label = path.relative_to(root.resolve()).as_posix()
        if label in chapters:
            raise ProjectError("Duplicate chapter in manuscript")
        chapters.append(label)
        text = read_utf8(path)
        current: list[str] = []
        start = 1
        number = 0

        def flush() -> None:
            nonlocal number
            if current:
                number += 1
                result.append(Paragraph(label, number, start, " ".join(current).strip()))
                current.clear()

        for line_number, line in enumerate(text.splitlines(), 1):
            if line.strip():
                if not current:
                    start = line_number
                current.append(line.strip())
            else:
                flush()
        flush()
    return result, chapters


def changes(old: list[Paragraph], new: list[Paragraph],
            old_order: list[str], new_order: list[str]) -> list[dict]:
    old_groups: dict[str, list[Paragraph]] = {}
    new_groups: dict[str, list[Paragraph]] = {}
    for p in old:
        old_groups.setdefault(p.chapter, []).append(p)
    for p in new:
        new_groups.setdefault(p.chapter, []).append(p)
    found = []
    for chapter in dict.fromkeys([*old_order, *new_order]):
        before, after = old_groups.get(chapter, []), new_groups.get(chapter, [])
        matcher = difflib.SequenceMatcher(
            None, [p.text for p in before], [p.text for p in after], autojunk=False
        )
        for tag, i, j, k, m in matcher.get_opcodes():
            if tag == "equal":
                continue
            found.append({
                "id": f"C{len(found)+1:04}", "chapter": chapter, "kind": tag,
                "before": [p.ref() for p in before[i:j]],
                "after": [p.ref() for p in after[k:m]],
            })
    return found


def words(text: str) -> set[str]:
    return {w.casefold() for w in WORD.findall(text) if len(w) > 2 and
            w.casefold() not in STOP and not w.isdigit()}


def candidates(change: dict, after: list[Paragraph], aliases: list[str] | None = None,
               max_hits: int = 12) -> list[dict]:
    texts = [p["excerpt"] for p in change["before"] + change["after"]]
    query = Counter(w for s in texts for w in words(s))
    # Significant names from a character dossier can be used even if no surface word survives.
    alias_set = {w for alias in (aliases or []) for w in words(alias)}
    query.update({w: 4 for w in alias_set})
    if not query:
        return []
    new_positions = {(p["chapter"], p["paragraph"]) for p in change["after"]}
    hits = []
    for p in after:
        if (p.chapter, p.number) in new_positions:
            continue
        tokens = words(p.text)
        overlap = tokens & query.keys()
        if not overlap:
            continue
        # Prefer distinctive words and known entity aliases; never claim this proves relevance.
        score = sum(min(query[w], 4) for w in overlap) + sum(7 for w in alias_set & tokens)
        if score < 2 and not alias_set:
            continue
        hits.append((score, p))
    # Mix high relevance with late-story coverage: a major consequence can occur
    # dozens of chapters later even when a name also appears in every early scene.
    positions = {(p.chapter, p.number): index for index, p in enumerate(after)}
    hits.sort(key=lambda item: (-item[0], positions[(item[1].chapter, item[1].number)]))
    focus = max(1, (max_hits * 2) // 3)
    selected = hits[:focus]
    picked = {(p.chapter, p.number) for _, p in selected}
    for score, p in sorted(hits, key=lambda item: positions[
            (item[1].chapter, item[1].number)], reverse=True):
        if len(selected) >= max_hits:
            break
        if (p.chapter, p.number) not in picked:
            selected.append((score, p))
            picked.add((p.chapter, p.number))
    return [{"relevance_score": score, **p.ref()} for score, p in selected]


def dossier(raw: dict) -> dict:
    if not isinstance(raw, dict) or raw.get("format_version") != 1:
        raise ProjectError("dossier: expected format_version = 1")
    facts, rules = raw.get("facts", []), raw.get("rules", [])
    if not isinstance(facts, list) or not isinstance(rules, list):
        raise ProjectError("dossier: facts and rules must be arrays")
    ids = set()
    for item in facts + rules:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"]:
            raise ProjectError("Every dossier fact and rule needs an id")
        if item["id"] in ids:
            raise ProjectError("Duplicate dossier ID: " + item["id"])
        ids.add(item["id"])
    fact_ids = {f["id"] for f in facts}
    rule_ids = {r["id"] for r in rules}
    for f in facts:
        for side in ("before", "after"):
            if not isinstance(f.get(side), str) or not f[side]:
                raise ProjectError(f"Fact {f['id']} requires nonempty {side} value")
        if not isinstance(f.get("label", f["id"]), str):
            raise ProjectError("Invalid fact label")
    for r in rules:
        groups = r.get("because_any")
        if not isinstance(groups, list) or not groups or any(not isinstance(g, list) or
                                                            not g for g in groups):
            raise ProjectError(f"Rule {r['id']} requires nonempty because_any groups")
        for group in groups:
            for condition in group:
                if not isinstance(condition, dict):
                    raise ProjectError("Invalid causal condition")
                if "fact" in condition:
                    if condition["fact"] not in fact_ids or not isinstance(condition.get("equals"), str):
                        raise ProjectError("Unknown fact or missing equals in " + r["id"])
                elif "rule" in condition:
                    if condition["rule"] not in rule_ids:
                        raise ProjectError("Unknown rule reference in " + r["id"])
                else:
                    raise ProjectError("Expected fact or rule condition in " + r["id"])
        terms = r.get("evidence_terms", [])
        if not isinstance(terms, list) or any(not isinstance(t, str) or len(t) < 3 for t in terms):
            raise ProjectError("Invalid evidence_terms in " + r["id"])
    return {"facts": facts, "rules": rules, "aliases": raw.get("aliases", [])}


def evaluate(spec: dict, side: str) -> dict:
    facts = {f["id"]: f for f in spec["facts"]}
    rules = {r["id"]: r for r in spec["rules"]}
    done: dict[str, dict] = {}
    visiting: set[str] = set()

    def solve(rule_id: str) -> dict:
        if rule_id in visiting:
            raise ProjectError("Causal dependency cycle at " + rule_id)
        if rule_id in done:
            return done[rule_id]
        visiting.add(rule_id)
        satisfied = []
        for i, group in enumerate(rules[rule_id]["because_any"]):
            compatible = True
            for condition in group:
                if "fact" in condition:
                    compatible &= facts[condition["fact"]][side].casefold() == condition["equals"].casefold()
                else:
                    compatible &= bool(solve(condition["rule"])["supported"])
            if compatible:
                satisfied.append(i)
        visiting.remove(rule_id)
        done[rule_id] = {"supported": bool(satisfied), "support_paths": satisfied}
        return done[rule_id]

    for rid in rules:
        solve(rid)
    return done


def evidence(pages: list[Paragraph], terms: list[str], max_hits: int = 15) -> tuple[int, list[dict]]:
    if not terms:
        return 0, []
    hits = [p.ref() for p in pages if any(term.casefold() in p.text.casefold() for term in terms)]
    return len(hits), hits[:max_hits]


def analyze(old_dir: Path, new_dir: Path, raw_dossier: dict | None = None,
            max_hits: int = 12) -> dict:
    if not 1 <= max_hits <= 50:
        raise ProjectError("max_hits must be between 1 and 50")
    old, old_sections = paragraphs(old_dir)
    new, new_sections = paragraphs(new_dir)
    diff = changes(old, new, old_sections, new_sections)
    spec = dossier(raw_dossier) if raw_dossier is not None else None
    aliases = spec["aliases"] if spec else []
    if not isinstance(aliases, list) or any(not isinstance(x, str) for x in aliases):
        raise ProjectError("aliases must be an array of strings")
    for change in diff:
        change["distant_candidates"] = candidates(change, new, aliases, max_hits)
    impact = []
    if spec:
        previous, current = evaluate(spec, "before"), evaluate(spec, "after")
        for fact in spec["facts"]:
            if fact["before"] != fact["after"]:
                used = [r["id"] for r in spec["rules"] if any(
                    condition.get("fact") == fact["id"]
                    for group in r["because_any"] for condition in group)]
                impact.append({"kind": "fact", "id": fact["id"],
                               "label": fact.get("label", fact["id"]),
                               "before": fact["before"], "after": fact["after"],
                               "direct_dependents": used,
                               "status": "linked_to_causality" if used else "no_declared_dependency"})
        for rule in spec["rules"]:
            rid = rule["id"]
            old_count, old_refs = evidence(old, rule.get("evidence_terms", []), max_hits)
            new_count, new_refs = evidence(new, rule.get("evidence_terms", []), max_hits)
            p, n = previous[rid], current[rid]
            if p["supported"] and not n["supported"]:
                status = "justification_lost_with_remaining_scene" if new_count else "justification_lost_scene_not_found"
            elif p["supported"] and n["supported"]:
                status = "alternative_justification" if p["support_paths"] != n["support_paths"] else "support_preserved"
            elif not p["supported"] and n["supported"]:
                status = "newly_justified"
            else:
                status = "unsupported_in_both"
            impact.append({
                "kind": "causal_rule", "id": rid, "label": rule.get("label", rid),
                "status": status, "old_support_paths": p["support_paths"],
                "new_support_paths": n["support_paths"],
                "old_mentions": old_count, "new_mentions": new_count,
                "old_evidence": old_refs, "new_evidence": new_refs,
                "review_note": rule.get("review_note", ""),
            })
    return {
        "format_version": 1, "mode": "dossier+retrieval" if spec else "retrieval_only",
        "disclaimer": "Candidate passages and declared causal rules are not a proof of literary consistency. "
                      "No natural-language causal inference is performed offline.",
        "old_chapters": len(old_sections), "new_chapters": len(new_sections),
        "changed_blocks": len(diff), "changes": diff, "impact": impact,
    }


def render_html(report: dict) -> str:
    def safe(value: object) -> str:
        return html.escape(str(value), quote=True)

    blocks = ['<!doctype html><html lang="fr"><head><meta charset="utf-8">',
              '<meta name="viewport" content="width=device-width,initial-scale=1">',
              '<title>Impacts narratifs</title><style>body{font:16px/1.6 system-ui;'
              'max-width:980px;margin:2rem auto;padding:1rem;background:#f8f8fa;color:#18202b}'
              'section{background:white;border:1px solid #ccd0db;padding:1.2rem;margin:1rem 0;'
              'border-radius:12px}pre{white-space:pre-wrap;overflow-wrap:anywhere}'
              'small{color:#515869}b{color:#1c3469}</style></head><body>',
              '<h1>Analyse d’impact narratif</h1>',
              f'<p>{safe(report["disclaimer"])}</p>',
              f'<p>{report["changed_blocks"]} blocs modifiés · {report["new_chapters"]} chapitres actuels</p>']
    for item in report["impact"]:
        blocks.extend(['<section>', f'<h2>{safe(item["label"])} · {safe(item["status"])}</h2>'])
        if item["kind"] == "fact":
            blocks.append(f'<p>Avant : {safe(item["before"])} · Après : {safe(item["after"])}</p>')
            blocks.append(f'<p>Dépendances déclarées : {safe(", ".join(item["direct_dependents"]) or "aucune")}</p>')
        else:
            blocks.append(f'<p>{safe(item["review_note"])}</p>')
            for reference in item["new_evidence"]:
                blocks.append(f'<p><small>{safe(reference["chapter"])} · §{reference["paragraph"]} · '
                              f'ligne {reference["line"]}</small><br>{safe(reference["excerpt"])}</p>')
        blocks.append('</section>')
    for item in report["changes"]:
        blocks.append(f'<section><h2>{safe(item["id"])} · {safe(item["chapter"])} · {safe(item["kind"])}</h2>')
        for title, key in (("Avant", "before"), ("Après", "after")):
            blocks.append(f'<h3>{title}</h3>')
            for p in item[key]:
                blocks.append(f'<p><small>§{p["paragraph"]} · ligne {p["line"]}</small><br>'
                              f'{safe(p["excerpt"])}</p>')
        blocks.append('<h3>Passages éloignés à examiner (similitude lexicale)</h3>')
        for p in item["distant_candidates"]:
            blocks.append(f'<p><small>{safe(p["chapter"])} · §{p["paragraph"]} · ligne '
                          f'{p["line"]} · score {p["relevance_score"]}</small><br>'
                          f'{safe(p["excerpt"])}</p>')
        blocks.append('</section>')
    return "\n".join([*blocks, "</body></html>"])


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Narrative causality impact review (offline by default)")
    parser.add_argument("old", type=Path, help="Old manuscript project (project.json + sections)")
    parser.add_argument("new", type=Path, help="Revised manuscript project")
    parser.add_argument("--dossier", type=Path, help="Optional fact/causality JSON annotations")
    parser.add_argument("--json-out", type=Path, help="Report JSON output path")
    parser.add_argument("--html-out", type=Path, help="Read-only HTML report output path")
    parser.add_argument("--max-hits", type=int, default=12)
    parser.add_argument("--force", action="store_true", help="Overwrite existing report files")
    args = parser.parse_args(argv)
    try:
        spec = json.loads(args.dossier.read_text(encoding="utf-8")) if args.dossier else None
        report = analyze(args.old, args.new, spec, args.max_hits)
        destinations = [x.resolve() for x in (args.json_out, args.html_out) if x]
        if len(set(destinations)) != len(destinations):
            raise ProjectError("Report paths must differ")
        protected = {(root.resolve() / "project.json").resolve()
                     for root in (args.old, args.new)}
        for root in (args.old, args.new):
            _, sources = load_project(root)
            protected.update(path.resolve() for path, _ in sources)
        if args.dossier:
            protected.add(args.dossier.resolve())
        for path in destinations:
            if path in protected:
                raise ProjectError("Report must not overwrite input manuscript or dossier")
            if path.exists() and (not args.force or not path.is_file()):
                raise ProjectError("Refusing to overwrite existing report: " + str(path))
            if path.resolve() in {x.resolve() for x in (args.old, args.new, args.dossier) if x}:
                raise ProjectError("Report must not overwrite input")
        if args.json_out:
            args.json_out.parent.mkdir(parents=True, exist_ok=True)
            args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if args.html_out:
            args.html_out.parent.mkdir(parents=True, exist_ok=True)
            args.html_out.write_text(render_html(report), encoding="utf-8")
        if not destinations:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(f"{report['changed_blocks']} modified blocks; {len(report['impact'])} dossier findings")
        return 0
    except (OSError, ValueError, UnicodeError) as exc:
        print("Narrative impact error: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(cli())
