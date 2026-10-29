#!/usr/bin/env python3
"""Generic, offline manuscript assembly and quality checks (Python 3.10+, stdlib)."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import statistics
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

WORD_RE = re.compile(r"[^\W_]+(?:[’'\-][^\W_]+)*", re.UNICODE)
SENTENCE_RE = re.compile(r"(?<=[.!?…])\s+")
MAX_SECTIONS = 500


class ProjectError(ValueError):
    pass


def count_words(text: str) -> int:
    return len(WORD_RE.findall(text))


def read_utf8(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")


def confined_file(root: Path, name: str) -> Path:
    if not isinstance(name, str) or not name or Path(name).is_absolute():
        raise ProjectError("File must be a nonempty relative path")
    candidate = (root / name).resolve()
    if not candidate.is_relative_to(root.resolve()) or candidate == root.resolve():
        raise ProjectError("Unsafe path outside project root: " + name)
    return candidate


def load_project(root: Path) -> tuple[dict, list[tuple[Path, str]]]:
    config_path = root / "project.json"
    try:
        data = json.loads(read_utf8(config_path))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProjectError("Cannot read project.json: " + str(exc)) from exc
    if not isinstance(data, dict) or data.get("format_version") != 1:
        raise ProjectError("project.json must specify format_version: 1")
    if not isinstance(data.get("title"), str) or not data["title"].strip():
        raise ProjectError("title must be a nonempty string")
    sections = data.get("sections")
    if not isinstance(sections, list) or not 1 <= len(sections) <= MAX_SECTIONS:
        raise ProjectError("sections must contain between 1 and 500 entries")
    minimum = data.get("minimum_words", 0)
    maximum = data.get("maximum_words", None)
    if type(minimum) is not int or minimum < 0:
        raise ProjectError("minimum_words must be a nonnegative integer")
    if maximum is not None and (type(maximum) is not int or maximum < minimum):
        raise ProjectError("maximum_words must be null or >= minimum_words")
    for name in ("required_phrases", "forbidden_phrases"):
        phrases = data.get(name, [])
        if not isinstance(phrases, list) or any(not isinstance(v, str) or not v.strip() for v in phrases):
            raise ProjectError(name + " must be a list of nonempty strings")
    paths = []
    seen = set()
    for number, section in enumerate(sections, 1):
        if not isinstance(section, dict):
            raise ProjectError("Section entries must be objects")
        heading = section.get("heading")
        if not isinstance(heading, str) or not heading.strip() or "\n" in heading:
            raise ProjectError("Invalid heading in section " + str(number))
        path = confined_file(root, section.get("file"))
        if path in seen or path == config_path.resolve():
            raise ProjectError("Duplicate or reserved section file: " + str(path))
        seen.add(path)
        paths.append((path, heading))
    return data, paths


def inspect(root: Path) -> tuple[dict, str, set[Path]]:
    project, sections = load_project(root)
    issues = []
    warnings = []
    breakdown = []
    texts = []
    paragraph_locations: dict[str, list[str]] = defaultdict(list)

    for index, (path, expected) in enumerate(sections, 1):
        label = path.relative_to(root.resolve()).as_posix()
        try:
            text = read_utf8(path)
        except (OSError, UnicodeError) as exc:
            issues.append({"code": "unreadable_section", "file": label, "detail": str(exc)})
            continue
        if "\x00" in text:
            issues.append({"code": "nul_character", "file": label})
            continue
        text = text.strip() + "\n"
        heading = next((s.strip() for s in text.splitlines() if s.strip()), "")
        if heading != expected:
            issues.append({"code": "heading_mismatch", "file": label,
                           "expected": expected, "found": heading[:120]})
        words = count_words(text)
        body = text.partition("\n")[2]
        sentences = [s for s in SENTENCE_RE.split(re.sub(r"\s+", " ", body).strip()) if s]
        sentence_sizes = [count_words(s) for s in sentences if count_words(s)]
        breakdown.append({
            "file": label, "heading": expected, "words": words,
            "characters": len(text), "paragraphs": len([p for p in re.split(r"\n\s*\n", body) if p.strip()]),
            "sentences": len(sentence_sizes),
            "average_sentence_words": round(statistics.mean(sentence_sizes), 1) if sentence_sizes else 0,
        })
        for paragraph in re.split(r"\n\s*\n", body):
            normalized = " ".join(paragraph.casefold().split())
            if len(normalized) >= 80:
                paragraph_locations[normalized].append(label)
        if any(line != line.rstrip() for line in text.splitlines()):
            warnings.append({"code": "trailing_whitespace", "file": label})
        if "\ufffd" in text:
            warnings.append({"code": "replacement_character", "file": label})
        texts.append(text.rstrip())

    manuscript = "\n\n\n".join(texts).rstrip() + "\n" if texts else ""
    total = count_words(manuscript)
    if len(texts) != len(sections):
        issues.append({"code": "incomplete_project", "readable": len(texts), "expected": len(sections)})
    if total < project.get("minimum_words", 0):
        issues.append({"code": "below_minimum_words", "actual": total, "minimum": project["minimum_words"]})
    maximum = project.get("maximum_words")
    if maximum is not None and total > maximum:
        issues.append({"code": "above_maximum_words", "actual": total, "maximum": maximum})
    for phrase in project.get("required_phrases", []):
        if phrase.casefold() not in manuscript.casefold():
            issues.append({"code": "required_phrase_missing", "phrase": phrase})
    for phrase in project.get("forbidden_phrases", []):
        if phrase.casefold() in manuscript.casefold():
            issues.append({"code": "forbidden_phrase", "phrase": phrase})
    for _, locations in paragraph_locations.items():
        if len(locations) > 1:
            warnings.append({"code": "repeated_long_paragraph", "files": locations, "occurrences": len(locations)})
    sizes = [s["words"] for s in breakdown]
    if len(sizes) >= 3 and statistics.median(sizes) > 0:
        median = statistics.median(sizes)
        for section in breakdown:
            if section["words"] < 0.45 * median:
                warnings.append({"code": "short_relative_section", "file": section["file"],
                                 "words": section["words"], "median_words": median})
    report = {
        "format_version": 1,
        "title": project["title"],
        "passed": not issues,
        "total_words": total,
        "section_count": len(sections),
        "readable_sections": len(texts),
        "sha256": hashlib.sha256(manuscript.encode("utf-8")).hexdigest() if manuscript else None,
        "sections": breakdown,
        "issues": issues,
        "warnings": warnings,
    }
    return report, manuscript, {path for path, _ in sections}


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         prefix=".manuscript-", suffix=".tmp", dir=path.parent,
                                         delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def safe_output(root: Path, name: str, sources: set[Path], overwrite: bool) -> Path:
    dest = confined_file(root, name)
    if dest in sources or dest == (root / "project.json").resolve():
        raise ProjectError("Output would overwrite project configuration or a source section")
    if dest.exists() and not overwrite:
        raise ProjectError("Output exists; use --force to replace it: " + name)
    if dest.exists() and not dest.is_file():
        raise ProjectError("Output target is not a file: " + name)
    return dest


def initialize(root: Path, chapters: int, title: str) -> None:
    if not 1 <= chapters <= 50:
        raise ProjectError("--chapters must be between 1 and 50")
    if not title.strip():
        raise ProjectError("--title must be nonempty")
    section_specs = [{"file": f"sections/chapter_{i:02d}.txt", "heading": f"Chapitre {i}"}
                     for i in range(1, chapters + 1)]
    paths = [root / "project.json"] + [root / entry["file"] for entry in section_specs]
    if any(path.exists() for path in paths):
        raise ProjectError("A target project file already exists; init does not overwrite")
    root.mkdir(parents=True, exist_ok=True)
    for section in section_specs:
        path = root / section["file"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(section["heading"] + "\n\n", encoding="utf-8")
    config = {
        "format_version": 1, "title": title, "minimum_words": 0,
        "maximum_words": None, "required_phrases": [], "forbidden_phrases": [],
        "sections": section_specs,
    }
    (root / "project.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n",
                                       encoding="utf-8")


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline, generic manuscript workflow")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="Create a project and empty chapter files")
    init.add_argument("root", type=Path)
    init.add_argument("--chapters", type=int, default=3)
    init.add_argument("--title", default="Mon manuscrit")
    for command in ("check", "build", "epub"):
        description = {"check": "Inspect sections", "build": "Assemble manuscript text",
                       "epub": "Export validated chapters to reflowable EPUB 3"}[command]
        p = sub.add_parser(command, help=description)
        p.add_argument("root", type=Path)
        p.add_argument("--json", action="store_true", help="Print structured report to stdout")
        if command in ("build", "epub"):
            p.add_argument("--output", default="manuscript.txt" if command == "build" else "manuscript.epub")
            p.add_argument("--force", action="store_true", help="Allow replacing existing output files")
        if command == "build":
            p.add_argument("--report", default="manuscript-report.json")
        if command == "epub":
            p.add_argument("--author", default="", help="Optional author metadata")
            p.add_argument("--language", default="fr", help="BCP47 language tag, default fr")
    args = parser.parse_args(argv)
    try:
        root = args.root.resolve()
        if args.command == "init":
            initialize(root, args.chapters, args.title)
            print("Created project: " + str(root))
            return 0
        report, manuscript, sources = inspect(root)
        if args.command == "epub" and report["passed"]:
            from epub_export import render_epub
            output = safe_output(root, args.output, sources, args.force)
            project, paths = load_project(root)
            chapters = []
            for chapter_path, heading in paths:
                lines = read_utf8(chapter_path).splitlines()
                first = next((i for i, line in enumerate(lines) if line.strip()), None)
                if first is None:
                    raise ProjectError("Empty section cannot be exported: " + heading)
                chapters.append((heading, "\n".join(lines[first + 1:])))
            render_epub(output, project["title"], chapters,
                        author=args.author, language=args.language)
        if args.command == "build" and report["passed"]:
            output = safe_output(root, args.output, sources, args.force)
            report_path = safe_output(root, args.report, sources, args.force)
            if output == report_path:
                raise ProjectError("Manuscript and report paths must differ")
            atomic_write(output, manuscript)
            atomic_write(report_path, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(f"{report['title']}: {report['total_words']} words, "
                  f"{report['readable_sections']}/{report['section_count']} sections; "
                  f"{len(report['issues'])} errors, {len(report['warnings'])} warnings")
            for issue in report["issues"]:
                print("ERROR " + json.dumps(issue, ensure_ascii=False))
            for warning in report["warnings"]:
                print("WARN  " + json.dumps(warning, ensure_ascii=False))
            if args.command == "build" and report["passed"]:
                print("Saved manuscript: " + str(output))
                print("Saved report: " + str(report_path))
            if args.command == "epub" and report["passed"]:
                print("Saved EPUB 3: " + str(output))
        return 0 if report["passed"] else 1
    except (ValueError, OSError, UnicodeError) as exc:
        print("Configuration error: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(cli())
