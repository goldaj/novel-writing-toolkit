from __future__ import annotations

import argparse
import json
import re
import statistics
from pathlib import Path


WORD_RE = re.compile(
    r"[A-Za-zÀ-ÖØ-öø-ÿŒœ0-9]+(?:['’\-][A-Za-zÀ-ÖØ-öø-ÿŒœ0-9]+)*"
)
HEADING_RE = re.compile(
    r"^(PROLOGUE|CHAPITRE\s+\d+|ÉPILOGUE|EPILOGUE)\b.*$",
    re.IGNORECASE,
)
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])(?:[»”\"])?\s+")


def words(text: str) -> list[str]:
    return WORD_RE.findall(text)


def normalized_heading(line: str) -> str | None:
    stripped = line.strip()
    match = HEADING_RE.match(stripped)
    return stripped if match else None


def chapter_sections(text: str) -> list[dict[str, object]]:
    lines = text.splitlines()
    starts: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        heading = normalized_heading(line)
        if heading:
            starts.append((index, heading))

    sections: list[dict[str, object]] = []
    for position, (start, heading) in enumerate(starts):
        end = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
        body = "\n".join(lines[start + 1 : end]).strip()
        sections.append(
            {
                "heading": heading,
                "line": start + 1,
                "words": len(words(body)),
                "characters": len(body),
            }
        )
    return sections


def sentence_metrics(text: str) -> dict[str, float | int]:
    flattened = re.sub(r"\s+", " ", text).strip()
    sentences = [
        sentence.strip()
        for sentence in SENTENCE_SPLIT_RE.split(flattened)
        if sentence.strip()
    ]
    lengths = [len(words(sentence)) for sentence in sentences if words(sentence)]
    if not lengths:
        return {
            "count": 0,
            "mean_words": 0,
            "median_words": 0,
            "p90_words": 0,
        }
    ordered = sorted(lengths)
    return {
        "count": len(lengths),
        "mean_words": round(statistics.mean(lengths), 2),
        "median_words": round(statistics.median(lengths), 2),
        "p90_words": ordered[int(0.9 * (len(ordered) - 1))],
    }


def analyze(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    nonempty_lines = [line.strip() for line in text.splitlines() if line.strip()]
    micro_lines = [line for line in nonempty_lines if len(words(line)) <= 3]
    sections = chapter_sections(text)

    watched_names = [
        "Takeshi",
        "Sayaka",
        "Hiroshi",
        "Keiji",
        "Aoi",
        "Kazuo",
        "Matsunaga",
        "Izanami",
        "Nakamura",
        "Kisaragi",
        "Harada",
        "Kaizen",
    ]
    name_counts = {
        name: len(re.findall(rf"\b{re.escape(name)}\b", text))
        for name in watched_names
    }

    return {
        "path": str(path.resolve()),
        "bytes": len(raw),
        "characters": len(text),
        "words": len(words(text)),
        "lines": text.count("\n") + 1,
        "nonempty_lines": len(nonempty_lines),
        "micro_lines_lte_3_words": len(micro_lines),
        "micro_line_percent": (
            round(100 * len(micro_lines) / len(nonempty_lines), 2)
            if nonempty_lines
            else 0
        ),
        "sentence_metrics": sentence_metrics(text),
        "part_heading_count": len(
            re.findall(r"^(?:.*\s+)?PARTIE\s+\d+\s*$", text, re.MULTILINE | re.IGNORECASE)
        ),
        "sections": sections,
        "name_counts": name_counts,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Mesure un manuscrit français UTF-8.")
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=Path(
            r"C:\Users\golda\Desktop\resurrectes\resurrectes_version_codex.txt"
        ),
    )
    parser.add_argument("--json", action="store_true", help="Sortie JSON compacte.")
    args = parser.parse_args()

    report = analyze(args.path)
    if args.json:
        print(json.dumps(report, ensure_ascii=False))
        return

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
