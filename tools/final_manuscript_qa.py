from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


DEFAULT_TARGET = Path(
    r"C:\Users\golda\Desktop\resurrectes\resurrectes_version_codex.txt"
)

WORD_RE = re.compile(
    r"[A-Za-zÀ-ÖØ-öø-ÿŒœ]+(?:[’'\-][A-Za-zÀ-ÖØ-öø-ÿŒœ]+)*"
)
HEADING_RE = re.compile(
    r"^(PROLOGUE|ÉPILOGUE|CHAPITRE ([1-9]|1[0-4]))(?:\s+—.*)?$",
    re.MULTILINE,
)

EXPECTED_HEADINGS = [
    "PROLOGUE — LA VALLÉE",
    "CHAPITRE 1 — ENTRER",
    "CHAPITRE 2 — LE PREMIER CHOC",
    "CHAPITRE 3 — CE QUI DÉRANGE",
    "CHAPITRE 4 — UNE MÉTHODE",
    "CHAPITRE 5 — LE DUEL STRATÉGIQUE",
    "CHAPITRE 6 — CEUX QU’ON COMMENCE À REGARDER",
    "CHAPITRE 7 — L’ARÈNE",
    "CHAPITRE 8 — IZANAMI",
    "CHAPITRE 9 — LA MATRICE DE CONCORDE",
    "CHAPITRE 10 — LE RETOUR",
    "CHAPITRE 11 — DE L’AUTRE CÔTÉ",
    "CHAPITRE 12 — LA MACHINE",
    "CHAPITRE 13 — CE QU’ON PRÉVOIT POUR ELLE",
    "CHAPITRE 14 — CHOISIR",
    "ÉPILOGUE — CE QUI RESTE OUVERT",
]

FORBIDDEN = [
    "CHAPITRE 2 — PARTIE",
    "\nBINÔMES\n",
    "Kaizen",
    "\ufffd",
    "Ã©",
    "â€™",
]

REQUIRED_CANON = [
    "Une personne ne revenait qu’une fois.",
    "La mort suivante de Sayaka serait définitive",
    "PROJECTION DYNASTIQUE",
    "PROTOCOLE DE SEUIL",
    "DÉCLARATION AUTHENTIFIÉE",
    "RÉVOCATION RÉSERVÉE AU PROFIL DÉCLARANT",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Contrôle final du manuscrit Résurrectés.")
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_TARGET)
    args = parser.parse_args()

    raw = args.path.read_bytes()
    text = raw.decode("utf-8", errors="strict")
    lines = text.splitlines()
    headings = [m.group(0) for m in HEADING_RE.finditer(text)]
    lexical_words = len(WORD_RE.findall(text))

    paragraphs = [
        re.sub(r"\s+", " ", paragraph.strip())
        for paragraph in re.split(r"\n\s*\n", text)
        if paragraph.strip()
    ]
    long_paragraph_counts = Counter(
        paragraph for paragraph in paragraphs if len(paragraph) >= 60
    )
    duplicated_long_paragraphs = [
        paragraph
        for paragraph, count in long_paragraph_counts.items()
        if count > 1
    ]

    forbidden_found = [item for item in FORBIDDEN if item in text]
    missing_canon = [item for item in REQUIRED_CANON if item not in text]
    trailing_whitespace_lines = [
        index
        for index, line in enumerate(lines, start=1)
        if line != line.rstrip()
    ]

    conservative_words_per_page = 360
    estimated_pages = lexical_words / conservative_words_per_page
    checks = {
        "utf8_strict": True,
        "expected_headings": headings == EXPECTED_HEADINGS,
        "heading_count_16": len(headings) == 16,
        "word_count_at_least_108000": lexical_words >= 108_000,
        "more_than_300_pages_at_360_words_per_page": estimated_pages > 300,
        "no_forbidden_artifacts": not forbidden_found,
        "required_canon_present": not missing_canon,
        "no_duplicate_long_paragraphs": not duplicated_long_paragraphs,
        "no_trailing_whitespace": not trailing_whitespace_lines,
        "no_tabs": "\t" not in text,
    }

    report = {
        "path": str(args.path),
        "sha256": hashlib.sha256(raw).hexdigest().upper(),
        "bytes": len(raw),
        "lexical_words": lexical_words,
        "estimated_pages_at_330_words": round(lexical_words / 330, 2),
        "estimated_pages_at_360_words": round(estimated_pages, 2),
        "headings": headings,
        "forbidden_found": forbidden_found,
        "missing_canon": missing_canon,
        "duplicate_long_paragraph_count": len(duplicated_long_paragraphs),
        "trailing_whitespace_lines": trailing_whitespace_lines,
        "checks": checks,
        "passed": all(checks.values()),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
