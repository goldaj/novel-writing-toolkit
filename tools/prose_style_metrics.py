from __future__ import annotations

import argparse
import json
import re
import statistics
from pathlib import Path


WORD_RE = re.compile(
    r"[A-Za-zÀ-ÖØ-öø-ÿŒœ]+(?:[’'\-][A-Za-zÀ-ÖØ-öø-ÿŒœ]+)*"
)
HEADING_RE = re.compile(r"^(?:PROLOGUE|ÉPILOGUE|CHAPITRE \d+)(?:\s+—.*)?$")
LABEL_RE = re.compile(r"^[A-ZÀ-ÖØ-Þ0-9][A-ZÀ-ÖØ-Þ0-9 ’'\-:,.]{4,}$")

TICS = [
    "regard",
    "silence",
    "légèrement",
    "une seconde",
    "quelque chose",
    "comme si",
    "net",
    "propre",
    "stable",
    "ligne",
    "flux",
    "structure",
    "tenir",
    "forcer",
    "céder",
]


def words(text: str) -> list[str]:
    return WORD_RE.findall(text)


def percentile(values: list[int], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    fraction = position - low
    return ordered[low] * (1 - fraction) + ordered[high] * fraction


def metrics(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    raw_blocks = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    paragraphs: list[str] = []
    for block in raw_blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        # Some source drafts encode each paragraph as a single line without blank
        # separators. Treat a long block as line-delimited prose so its cadence is
        # comparable with the later chapters.
        if len(lines) > 5:
            paragraphs.extend(lines)
        else:
            paragraphs.append(block)

    narrative: list[str] = []
    dialogue: list[str] = []
    for paragraph in paragraphs:
        first = paragraph.splitlines()[0].strip()
        if HEADING_RE.fullmatch(first) or LABEL_RE.fullmatch(paragraph):
            continue
        if first.startswith(("—", "–", "- ")):
            dialogue.append(paragraph)
        else:
            narrative.append(paragraph)

    narrative_lengths = [len(words(paragraph)) for paragraph in narrative]
    dialogue_lengths = [len(words(paragraph)) for paragraph in dialogue]
    lexical_count = len(words(text))
    lowered = text.casefold()

    tic_counts: dict[str, dict[str, float | int]] = {}
    for tic in TICS:
        count = len(re.findall(rf"(?<!\w){re.escape(tic.casefold())}(?!\w)", lowered))
        tic_counts[tic] = {
            "count": count,
            "per_10k": round((count * 10_000 / lexical_count), 2)
            if lexical_count
            else 0.0,
        }

    micro = sum(length <= 3 for length in narrative_lengths)
    return {
        "path": str(path.resolve()),
        "lexical_words": lexical_count,
        "paragraphs": len(paragraphs),
        "narrative_paragraphs": len(narrative),
        "dialogue_paragraphs": len(dialogue),
        "narrative_words": {
            "mean": round(statistics.mean(narrative_lengths), 2)
            if narrative_lengths
            else 0.0,
            "median": round(statistics.median(narrative_lengths), 2)
            if narrative_lengths
            else 0.0,
            "p90": round(percentile(narrative_lengths, 0.9), 2),
            "micro_lte_3": micro,
            "micro_percent": round(100 * micro / len(narrative_lengths), 2)
            if narrative_lengths
            else 0.0,
        },
        "dialogue_words": {
            "mean": round(statistics.mean(dialogue_lengths), 2)
            if dialogue_lengths
            else 0.0,
            "median": round(statistics.median(dialogue_lengths), 2)
            if dialogue_lengths
            else 0.0,
        },
        "tics": tic_counts,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()
    reports = [metrics(path) for path in args.paths]
    print(json.dumps(reports[0] if len(reports) == 1 else reports, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
