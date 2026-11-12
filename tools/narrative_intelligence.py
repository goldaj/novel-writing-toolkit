#!/usr/bin/env python3
"""Narrative Intelligence Engine: offline CLI and private, browsable reports."""
from __future__ import annotations

import argparse
import html
import json
import os
import sys
import tempfile
from pathlib import Path

from manuscript_pipeline import ProjectError, load_project
from narrative_memory import read_memory, audit, compare


def h(value: object) -> str:
    return html.escape(str(value), quote=True)


def source_link(source: dict) -> str:
    return ("<span class='source'>" + h(source.get("chapter", "?")) +
            " · « " + h(source.get("quote", "")[:240]) + " »</span>")


def _card(title: str, body: str, key: str = "") -> str:
    return ("<article class='card' data-search='" + h(key) + "'><h3>" +
            h(title) + "</h3>" + body + "</article>")


def _section(title: str, inner: str, ident: str) -> str:
    return ("<section id='" + ident + "'><h2>" + h(title) +
            "</h2>" + (inner or "<p class='muted'>Aucun élément documenté.</p>") + "</section>")


def render_html(report: dict) -> str:
    """Render a standalone HTML report: no external assets or network requests."""
    is_comparison = report["kind"] == "narrative_comparison"
    current = report["after"] if is_comparison else report
    counts = current["counts"]
    chunks = [
        "<!doctype html><html lang='fr'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        "<title>Narrative Intelligence | Rapport local</title>",
        "<style>",
        ":root{color-scheme:light;--bg:#f6f6f8;--ink:#202638;--muted:#5d6574;"
        "--line:#dfe3eb;--accent:#435eb4;--paper:#fff}",
        "*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);"
        "font:16px/1.55 system-ui,-apple-system,sans-serif}",
        "header{background:#1f2941;color:white;padding:2rem max(1.2rem,calc((100vw - 1080px)/2))}",
        "header p{max-width:900px;color:#e6e9f4}header h1{font-size:clamp(1.7rem,4vw,2.5rem);margin:.2rem 0}",
        "main{max-width:1080px;margin:0 auto;padding:1rem 1.2rem 4rem}",
        "nav{display:flex;flex-wrap:wrap;gap:.7rem;margin:1rem 0 1.4rem}",
        "nav a{color:var(--accent);padding:.4rem .75rem;background:white;border-radius:.4rem;"
        "border:1px solid var(--line);text-decoration:none}",
        "h2{margin:2.2rem 0 1rem;font-size:1.35rem}",
        ".stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:.6rem}",
        ".stat,.card{background:var(--paper);border:1px solid var(--line);border-radius:12px;padding:1rem}",
        ".stat b{font-size:1.7rem;display:block}.stat span,.muted,.source{color:var(--muted)}",
        ".cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(265px,1fr));gap:.75rem}",
        ".card h3{font-size:1rem;margin:0 0 .5rem;overflow-wrap:anywhere}",
        ".card p{margin:.4rem 0;overflow-wrap:anywhere}.source{font-size:.83rem;display:block}",
        ".pill{font-size:.72rem;border-radius:9px;background:#e8ebf8;color:#263f87;"
        "padding:.2rem .5rem;font-weight:600;display:inline-block;margin:.1rem}",
        "details{border:1px solid var(--line);border-radius:10px;padding:.8rem 1rem;background:white;margin:.5rem 0}",
        "summary{cursor:pointer;font-weight:600}blockquote{margin:.5rem 0;padding:.5rem .8rem;"
        "background:#f4f6fa;border-left:3px solid #99a9d2;white-space:pre-wrap}",
        "input[type=search]{width:100%;padding:.8rem 1rem;border:1px solid #b3bad0;border-radius:8px;"
        "font:inherit;background:white}a{color:#3653a3}footer{margin-top:3rem;color:var(--muted);"
        "font-size:.9rem}@media print{header{background:white;color:black;padding:1rem 0}"
        "nav,input{display:none}main{padding:0}.card,details{break-inside:avoid}}",
        "</style></head><body><header><p>RAPPORT LOCAL · HORS LIGNE</p>",
        "<h1>Narrative Intelligence Engine</h1>",
        "<p>" + h(report["notice"]) + "</p></header><main>",
        "<div class='stats'>"
    ]
    for key, label in (("characters", "Personnages"), ("events", "Événements"),
                       ("facts", "Faits"), ("knowledge", "États de connaissance"),
                       ("dependencies", "Relations causales")):
        chunks.append("<div class='stat'><b>" + str(counts[key]) +
                      "</b><span>" + label + "</span></div>")
    chunks.append("</div><nav><a href='#chronology'>Chronologie</a>"
                  "<a href='#characters'>Personnages</a><a href='#facts'>Faits</a>"
                  "<a href='#issues'>Vérifications</a>")
    if is_comparison:
        chunks.append("<a href='#impacts'>Révisions et impacts</a>")
    chunks.append("</nav><label for='filter'>Filtrer les éléments du rapport</label>"
                  "<input id='filter' type='search' placeholder='Personnage, fait, événement…' "
                  "aria-label='Filtrer les cartes'>")
    chronology = []
    for event in current["timeline"]:
        when = ("Temps " + str(event["time_index"]) if event["time_index"] is not None
                else "Temps indéterminé")
        body = ("<span class='pill'>" + when + "</span><p>" +
                source_link(event["source"]) + "</p>")
        if event["participants"]:
            body += "<p>Participants : " + h(", ".join(event["participants"])) + "</p>"
        state = current["causal_support"].get(event["id"])
        if state and state["declared"]:
            body += "<p>Prérequis déclarés : <strong>" + h(state["state"]) + "</strong></p>"
        chronology.append(_card(event["id"] + " · " + event["label"], body,
                                event["id"] + " " + event["label"]))
    chunks.append(_section("Chronologie annotée", "<div class='cards'>" +
                           "".join(chronology) + "</div>", "chronology"))
    characters = []
    for character in current["characters"]:
        cid = character["id"]
        possessed = [k for k in current["knowledge"] if k["character"] == cid]
        body = "<p>Alias : " + h(", ".join(character.get("aliases", [])) or "aucun") + "</p>"
        if possessed:
            body += "<ul>" + "".join("<li><strong>" + h(k["fact"]) + "</strong> : " +
                                       h(k["state"]) + " · " +
                                       h(k.get("since_event", "date non renseignée")) +
                                       "</li>" for k in possessed) + "</ul>"
        characters.append(_card(character["name"] + " · " + cid, body, cid + " " + character["name"]))
    chunks.append(_section("Personnages et connaissances", "<div class='cards'>" +
                           "".join(characters) + "</div>", "characters"))
    facts = []
    for fact in current["facts"]:
        body = ("<p>" + h(fact["subject"]) + " / " + h(fact["attribute"]) + " : <strong>" +
                h(fact["value"]) + "</strong></p><p>" + source_link(fact["source"]) + "</p>" +
                "<span class='pill'>" + h(fact.get("confidence", "confirmed")) + "</span>")
        facts.append(_card(fact["id"], body, fact["id"] + " " + fact["subject"] + " " + fact["attribute"]))
    chunks.append(_section("Faits et états du monde", "<div class='cards'>" +
                           "".join(facts) + "</div>", "facts"))
    issues = []
    for issue in current["issues"]:
        detail = "<p>" + h(issue.get("detail", "Révision recommandée")) + "</p>"
        important = " · ".join(str(issue.get(k)) for k in ("event", "item", "character", "fact", "chapter")
                               if issue.get(k))
        if important:
            detail += "<p class='muted'>" + h(important) + "</p>"
        if issue.get("facts"):
            detail += "<p>Faits concernés : " + h(", ".join(issue["facts"])) + "</p>"
        issues.append(_card(issue["code"], detail, str(issue)))
    chunks.append(_section("Points à examiner (" + str(len(issues)) + ")",
                           "<div class='cards'>" + "".join(issues) + "</div>", "issues"))
    if is_comparison:
        boxes = []
        for change in report["memory_changes"]:
            boxes.append(_card(change["kind"] + " · " + change["id"],
                               "<p><span class='pill'>" + h(change["change"]) + "</span></p>",
                               str(change)))
        for impact in report["consequences"]:
            boxes.append(_card("Conséquence : " + impact["event"],
                               "<p>" + h(impact["before"]) + " → " + h(impact["after"]) +
                               "</p><p><strong>" + h(impact["status"]) + "</strong></p>" +
                               "<p>" + source_link(impact["source"]) + "</p>", str(impact)))
        chunks.append(_section("Changements de mémoire et conséquences",
                               "<p>" + str(report["changed_blocks"]) +
                               " bloc(s) textuel(s) modifié(s) identifiés par le comparateur existant.</p>"
                               "<div class='cards'>" + "".join(boxes) + "</div>", "impacts"))
        all_diffs = report["text_changes"]
        for change in all_diffs[:100]:
            body = []
            for label, key in (("Avant", "before"), ("Après", "after")):
                body.append("<strong>" + label + "</strong>")
                body.extend("<blockquote>" + h(p["excerpt"]) + "</blockquote>"
                            for p in change[key][:8])
            chunks.append("<details><summary>" + h(change["id"] + " · " + change["chapter"]) +
                          " (" + h(change["kind"]) + ")</summary>" + "".join(body) + "</details>")
        if len(all_diffs) > 100:
            chunks.append("<p>" + str(len(all_diffs) - 100) +
                          " blocs supplémentaires sont disponibles dans le rapport JSON.</p>")
    chunks.append("<footer>Ce rapport rassemble des annotations et des pistes de relecture. "
                  "Il n'établit jamais à lui seul la cohérence littéraire du manuscrit. "
                  "Données locales : ne pas publier ce fichier sans vérification.</footer></main>"
                  "<script>document.getElementById('filter').addEventListener('input',function(){"
                  "var q=this.value.toLocaleLowerCase('fr');"
                  "document.querySelectorAll('.card').forEach(function(card){"
                  "card.hidden=!card.textContent.toLocaleLowerCase('fr').includes(q);});});"
                  "</script></body></html>")
    return "\n".join(chunks)


def protected_paths(projects: list[Path], memories: list[Path]) -> set[Path]:
    paths = {m.resolve() for m in memories}
    for project in projects:
        paths.add((project.resolve() / "project.json").resolve())
        _info, sections = load_project(project.resolve())
        paths.update(p.resolve() for p, _ in sections)
    return paths


def write_outputs(report: dict, json_path: Path | None, html_path: Path | None,
                  projects: list[Path], memories: list[Path], force: bool) -> None:
    destination = [p.resolve() for p in (json_path, html_path) if p is not None]
    if len(set(destination)) != len(destination):
        raise ProjectError("Report outputs must be distinct")
    forbidden = protected_paths(projects, memories)
    for path in destination:
        if path in forbidden or path.is_dir():
            raise ProjectError("Refusing to overwrite an input or a directory: " + str(path))
        if path.exists() and not force:
            raise ProjectError("Report exists; add --force explicitly: " + str(path))
    payloads = []
    if json_path is not None:
        payloads.append((json_path, json.dumps(report, ensure_ascii=False, indent=2) + "\n"))
    if html_path is not None:
        payloads.append((html_path, render_html(report)))
    for path, content in payloads:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                             prefix=".narrative-", suffix=".tmp",
                                             delete=False) as handle:
                temp = Path(handle.name)
                handle.write(content)
            os.replace(temp, path)
        finally:
            if temp is not None and temp.exists():
                temp.unlink()


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline narrative memory and revision analysis")
    sub = parser.add_subparsers(dest="command", required=True)
    a = sub.add_parser("audit", help="Validate and explore one annotated manuscript")
    a.add_argument("project", type=Path)
    a.add_argument("memory", type=Path)
    b = sub.add_parser("compare", help="Compare two versions and trace narrative impact")
    b.add_argument("before_project", type=Path)
    b.add_argument("after_project", type=Path)
    b.add_argument("before_memory", type=Path)
    b.add_argument("after_memory", type=Path)
    for subparser in (a, b):
        subparser.add_argument("--json-out", type=Path)
        subparser.add_argument("--html-out", type=Path)
        subparser.add_argument("--force", action="store_true", help="Explicitly replace reports")
    args = parser.parse_args(argv)
    try:
        if args.command == "audit":
            projects, memories = [args.project], [args.memory]
            report = audit(args.project, read_memory(args.memory))
        else:
            projects = [args.before_project, args.after_project]
            memories = [args.before_memory, args.after_memory]
            report = compare(args.before_project, args.after_project,
                             read_memory(args.before_memory), read_memory(args.after_memory))
        write_outputs(report, args.json_out, args.html_out, projects, memories, args.force)
        if args.json_out is None and args.html_out is None:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            status = report["after"] if args.command == "compare" else report
            print("Narrative report: " + str(len(status["issues"])) + " review items; " +
                  str(status["counts"]["events"]) + " annotated events")
        return 0
    except (OSError, UnicodeError, ValueError) as exc:
        print("Narrative Intelligence error: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(cli())
