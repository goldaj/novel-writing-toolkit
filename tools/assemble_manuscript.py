from __future__ import annotations

import argparse
import os
import re
import tempfile
from pathlib import Path


TARGET = Path(r"./manuscript.txt")
WORK_ROOT = Path(r"./manuscript_work")
DRAFT_DIR = WORK_ROOT / "draft"

SECTION_FILES = [
    "prologue.txt",
    "chapter_01.txt",
    "chapter_02.txt",
    "chapter_03.txt",
    "chapter_04.txt",
    "chapter_05.txt",
    "chapter_06.txt",
    "chapter_07.txt",
    "chapter_08.txt",
    "chapter_09.txt",
    "chapter_10.txt",
    "chapter_11.txt",
    "chapter_12.txt",
    "chapter_13.txt",
    "chapter_14.txt",
    "epilogue.txt",
]

EXPECTED_HEADINGS = [
    "PROLOGUE",
    "CHAPITRE 1",
    "CHAPITRE 2",
    "CHAPITRE 3",
    "CHAPITRE 4",
    "CHAPITRE 5",
    "CHAPITRE 6",
    "CHAPITRE 7",
    "CHAPITRE 8",
    "CHAPITRE 9",
    "CHAPITRE 10",
    "CHAPITRE 11",
    "CHAPITRE 12",
    "CHAPITRE 13",
    "CHAPITRE 14",
    "ÉPILOGUE",
]

WORD_RE = re.compile(
    r"[A-Za-zÀ-ÖØ-öø-ÿŒœ]+(?:[’'\-][A-Za-zÀ-ÖØ-öø-ÿŒœ]+)*"
)


def lexical_words(text: str) -> int:
    return len(WORD_RE.findall(text))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Assemble all revised section files into the requested target."
    )
    parser.add_argument(
        "--minimum-words",
        type=int,
        default=100_000,
        help="Refuse assembly if the manuscript is shorter than this lexical word count.",
    )
    args = parser.parse_args()

    missing = [name for name in SECTION_FILES if not (DRAFT_DIR / name).exists()]
    if missing:
        raise FileNotFoundError("Missing manuscript sections: " + ", ".join(missing))

    sections: list[str] = []
    manifest_lines: list[str] = []
    for index, (name, expected) in enumerate(
        zip(SECTION_FILES, EXPECTED_HEADINGS, strict=True), start=1
    ):
        path = DRAFT_DIR / name
        text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").strip()
        first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
        if not first_line.startswith(expected):
            raise ValueError(
                f"{name}: expected a heading starting with {expected!r}, got {first_line!r}"
            )
        if "CHAPITRE 2 — PARTIE" in text:
            raise ValueError(f"{name}: obsolete part heading remains")
        words = lexical_words(text)
        manifest_lines.append(f"{index:02d}\t{name}\t{words}")
        sections.append(text)

    manuscript = "\n\n\n".join(sections).rstrip() + "\n"
    total_words = lexical_words(manuscript)
    if total_words < args.minimum_words:
        raise ValueError(
            f"Manuscript too short: {total_words} words; minimum is {args.minimum_words}"
        )

    headings = [
        line.strip()
        for line in manuscript.splitlines()
        if re.fullmatch(r"(?:PROLOGUE|ÉPILOGUE|CHAPITRE \d+)(?:\s+—.*)?", line.strip())
    ]
    if len(headings) != len(SECTION_FILES):
        raise ValueError(
            f"Expected {len(SECTION_FILES)} main headings, found {len(headings)}: {headings}"
        )

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        dir=TARGET.parent,
        prefix=TARGET.stem + "_",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(manuscript)
        temp_path = Path(handle.name)
    os.replace(temp_path, TARGET)

    manifest = "\n".join(manifest_lines)
    manifest += f"\nTOTAL\tresurrectes_version_codex.txt\t{total_words}\n"
    (WORK_ROOT / "assembly_manifest.txt").write_text(
        manifest,
        encoding="utf-8",
        newline="\n",
    )

    print(f"Assembled {len(sections)} sections")
    print(f"Lexical words: {total_words}")
    print(f"Target: {TARGET}")


if __name__ == "__main__":
    main()
