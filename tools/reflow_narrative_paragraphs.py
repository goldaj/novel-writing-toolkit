from __future__ import annotations

import argparse
import re
from pathlib import Path


WORD_RE = re.compile(
    r"[A-Za-zÀ-ÖØ-öø-ÿŒœ]+(?:[’'\-][A-Za-zÀ-ÖØ-öø-ÿŒœ]+)*"
)
HEADING_RE = re.compile(r"^(?:PROLOGUE|ÉPILOGUE|CHAPITRE \d+)(?:\s+—.*)?$")
LABEL_RE = re.compile(r"^[A-ZÀ-ÖØ-Þ0-9][A-ZÀ-ÖØ-Þ0-9 ’'\-:,.]{4,}$")

PRESERVE = {
    "Une fois.",
    "Il était mort.",
    "Il est mort.",
    "Rien.",
    "Non.",
    "Oui.",
    "Rien n’avait cessé.",
    "Elle disait non.",
    "Et personne n’avait pu la faire revenir.",
    "CAS DE RÉSURRECTION CONFIRMÉ",
}


def word_count(text: str) -> int:
    return len(WORD_RE.findall(text))


def paragraphs(text: str) -> list[str]:
    raw_blocks = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    result: list[str] = []
    for block in raw_blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) > 5:
            result.extend(lines)
        else:
            result.append(" ".join(lines))
    return result


def kind(paragraph: str) -> str:
    first = paragraph.splitlines()[0].strip()
    if HEADING_RE.fullmatch(first):
        return "heading"
    if first.startswith(("—", "–", "- ")):
        return "dialogue"
    if LABEL_RE.fullmatch(paragraph):
        return "label"
    if paragraph in PRESERVE:
        return "impact"
    return "narrative"


def merge_run(run: list[str], minimum: int, maximum: int) -> list[str]:
    output: list[str] = []
    buffer: list[str] = []
    buffer_words = 0

    def flush() -> None:
        nonlocal buffer, buffer_words
        if buffer:
            output.append(" ".join(buffer))
            buffer = []
            buffer_words = 0

    for paragraph in run:
        count = word_count(paragraph)
        if count >= minimum:
            if buffer:
                combined = buffer_words + count
                if combined <= maximum:
                    buffer.append(paragraph)
                    flush()
                else:
                    flush()
                    output.append(paragraph)
            else:
                output.append(paragraph)
            continue

        if buffer_words + count <= maximum:
            buffer.append(paragraph)
            buffer_words += count
            if buffer_words >= minimum:
                flush()
        else:
            flush()
            buffer.append(paragraph)
            buffer_words = count

    if buffer:
        if output and word_count(output[-1]) + buffer_words <= maximum:
            output[-1] = output[-1] + " " + " ".join(buffer)
        else:
            flush()
    return output


def reflow(text: str, minimum: int, maximum: int) -> str:
    source = paragraphs(text.replace("\r\n", "\n"))
    result: list[str] = []
    run: list[str] = []

    def flush_run() -> None:
        nonlocal run
        if run:
            result.extend(merge_run(run, minimum, maximum))
            run = []

    for paragraph in source:
        if kind(paragraph) == "narrative":
            run.append(paragraph)
        else:
            flush_run()
            result.append(paragraph)
    flush_run()
    return "\n\n".join(result).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Conservatively merge adjacent short narrative paragraphs."
    )
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--minimum", type=int, default=14)
    parser.add_argument("--maximum", type=int, default=60)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    for path in args.paths:
        text = path.read_text(encoding="utf-8-sig")
        result = reflow(text, args.minimum, args.maximum)
        before = len(paragraphs(text))
        after = len(paragraphs(result))
        print(f"{path}: paragraphs {before} -> {after}")
        if args.write:
            path.write_text(result, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
