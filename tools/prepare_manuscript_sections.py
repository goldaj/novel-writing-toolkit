from __future__ import annotations

import argparse
import shutil
from pathlib import Path


TARGET = Path(r"./manuscript.txt")
WORK_ROOT = Path(r"./manuscript_work")
DRAFT_DIR = WORK_ROOT / "draft"


def section(text: str, start: str, end: str | None) -> str:
    start_at = text.find(start)
    if start_at < 0:
        raise ValueError(f"Heading not found: {start!r}")
    if end is None:
        return text[start_at:].strip()
    end_at = text.find(end, start_at + len(start))
    if end_at < 0:
        raise ValueError(f"Following heading not found: {end!r}")
    return text[start_at:end_at].strip()


def write_section(path: Path, content: str, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(
            f"{path} already exists; pass --force only when intentionally rebuilding it."
        )
    path.write_text(content.rstrip() + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Split the original target prefix into revision-friendly sections."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the generated section files.",
    )
    args = parser.parse_args()

    if not TARGET.exists():
        raise FileNotFoundError(TARGET)

    DRAFT_DIR.mkdir(parents=True, exist_ok=True)
    backup = WORK_ROOT / "original_target_before_assembly.txt"
    if not backup.exists():
        shutil.copyfile(TARGET, backup)

    text = TARGET.read_text(encoding="utf-8-sig").replace("\r\n", "\n")

    prologue = section(text, "PROLOGUE — LA VALLÉE", "CHAPITRE 1")
    chapter_01 = section(text, "CHAPITRE 1", "CHAPITRE 2 — PARTIE 1")
    chapter_02_part_1 = section(
        text,
        "CHAPITRE 2 — PARTIE 1",
        "CHAPITRE 2 — PARTIE 2",
    )
    chapter_02_part_2 = section(text, "CHAPITRE 2 — PARTIE 2", None)

    chapter_02_part_1 = chapter_02_part_1.replace(
        "CHAPITRE 2 — PARTIE 1",
        "CHAPITRE 2 — LE PREMIER CHOC",
        1,
    )
    chapter_02_part_2 = chapter_02_part_2.replace(
        "CHAPITRE 2 — PARTIE 2",
        "",
        1,
    ).strip()

    continuation_path = DRAFT_DIR / "chapter_02_continuation.txt"
    if not continuation_path.exists():
        raise FileNotFoundError(continuation_path)
    continuation = continuation_path.read_text(encoding="utf-8-sig").strip()
    chapter_02 = "\n\n".join(
        (chapter_02_part_1.strip(), chapter_02_part_2, continuation)
    )

    write_section(DRAFT_DIR / "prologue.txt", prologue, args.force)
    write_section(DRAFT_DIR / "chapter_01.txt", chapter_01, args.force)
    write_section(DRAFT_DIR / "chapter_02.txt", chapter_02, args.force)

    print(f"Prepared: {DRAFT_DIR / 'prologue.txt'}")
    print(f"Prepared: {DRAFT_DIR / 'chapter_01.txt'}")
    print(f"Prepared: {DRAFT_DIR / 'chapter_02.txt'}")
    print(f"Backup:   {backup}")


if __name__ == "__main__":
    main()
