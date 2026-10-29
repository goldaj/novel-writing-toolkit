"""Minimal, standards-oriented EPUB 3 exporter (stdlib; offline; no private data upload).

Expects already validated chapter titles and texts from manuscript_pipeline.
"""
from __future__ import annotations

import hashlib
import html
import os
import re
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

XML_NS = "http://www.w3.org/1999/xhtml"
EPUB_NS = "http://www.idpf.org/2007/ops"
OPF_NS = "http://www.idpf.org/2007/opf"
DC_NS = "http://purl.org/dc/elements/1.1/"
LANGUAGE = re.compile(r"^[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")


def safe_xml(value: str) -> str:
    """Reject XML 1.0 forbidden codepoints instead of producing unreadable EPUBs."""
    for character in value:
        code = ord(character)
        if code < 32 and code not in (9, 10, 13):
            raise ValueError("Manuscript contains XML-incompatible control characters")
        if 0xD800 <= code <= 0xDFFF or code in (0xFFFE, 0xFFFF):
            raise ValueError("Manuscript contains invalid Unicode code points")
    return html.escape(value, quote=True)


def chapter_body(body: str) -> str:
    """Render plain paragraphs and simple Markdown headings; never embed source HTML."""
    parts = []
    paragraphs: list[str] = []

    def flush():
        if paragraphs:
            paragraph = " ".join(line.strip() for line in paragraphs)
            parts.append("<p>" + safe_xml(paragraph) + "</p>")
            paragraphs.clear()

    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            flush()
        elif stripped.startswith("## "):
            flush()
            parts.append("<h3>" + safe_xml(stripped[3:].strip()) + "</h3>")
        else:
            paragraphs.append(line)
    flush()
    return "\n".join(parts) or "<p></p>"


def xhtml(title: str, body: str, language: str) -> bytes:
    title_escaped = safe_xml(title)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<html xmlns="{XML_NS}" xml:lang="{language}" lang="{language}">'
        '<head><meta charset="UTF-8"/><title>' + title_escaped +
        '</title><link rel="stylesheet" type="text/css" href="../styles/main.css"/></head>'
        '<body><section><h2>' + title_escaped + '</h2>\n' +
        chapter_body(body) + '</section></body></html>'
    ).encode("utf-8")


def render_epub(path: Path, title: str, sections: list[tuple[str, str]], *,
                author: str = "", language: str = "fr") -> None:
    """Atomically write a reflowable EPUB 3 from validated manuscript sections."""
    if not sections or len(sections) > 500:
        raise ValueError("EPUB requires 1–500 sections")
    if not LANGUAGE.fullmatch(language):
        raise ValueError("Invalid language code")
    safe_xml(title)
    safe_xml(author)
    for heading, text in sections:
        safe_xml(heading)
        safe_xml(text)
    from xml.etree import ElementTree as ET

    digest = hashlib.sha256(("\n".join([title, author] + [h + "\n" + b for h, b in sections])).encode("utf-8")).hexdigest()
    identifier = "urn:uuid:" + digest[:8] + "-" + digest[8:12] + "-" + digest[12:16] + "-" + digest[16:20] + "-" + digest[20:32]
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    links = "".join(
        f'<li><a href="text/chapter-{i:03d}.xhtml">{safe_xml(heading)}</a></li>'
        for i, (heading, _) in enumerate(sections, 1)
    )
    nav = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<html xmlns="{XML_NS}" xmlns:epub="{EPUB_NS}" xml:lang="{language}">'
        '<head><title>Table des matières</title></head><body>'
        '<nav epub:type="toc" id="toc"><h1>Sommaire</h1><ol>' + links +
        '</ol></nav></body></html>'
    ).encode("utf-8")
    manifest = '\n'.join(
        f'<item id="chapter-{i}" href="text/chapter-{i:03d}.xhtml" media-type="application/xhtml+xml"/>'
        for i in range(1, len(sections) + 1)
    )
    spine = '\n'.join(f'<itemref idref="chapter-{i}"/>' for i in range(1, len(sections) + 1))
    author_element = '<dc:creator>' + safe_xml(author) + '</dc:creator>' if author.strip() else ''
    opf = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<package xmlns="{OPF_NS}" xmlns:dc="{DC_NS}" version="3.0" unique-identifier="book-id">'
        '<metadata><dc:identifier id="book-id">' + identifier + '</dc:identifier>'
        '<dc:title>' + safe_xml(title) + '</dc:title>'
        '<dc:language>' + language + '</dc:language>' + author_element +
        '<meta property="dcterms:modified">' + stamp + '</meta></metadata>'
        '<manifest><item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
        '<item id="css" href="styles/main.css" media-type="text/css"/>' + manifest +
        '</manifest><spine>' + spine + '</spine></package>'
    ).encode("utf-8")
    container = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
        '<rootfiles><rootfile full-path="EPUB/package.opf" '
        'media-type="application/oebps-package+xml"/></rootfiles></container>'
    ).encode("utf-8")
    css = b"body { font-family: serif; line-height: 1.5; margin: 5%; } h2 { break-before: page; } p { text-indent: 1.2em; margin: 0 0 .75em; }"

    # Fail before replacing destination if generated metadata/markup is malformed.
    for document in (nav, opf, container):
        ET.fromstring(document)
    for heading, body in sections:
        ET.fromstring(xhtml(heading, body, language))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".epub-", suffix=".tmp", dir=path.parent, delete=False) as out:
            temporary = Path(out.name)
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
            archive.writestr("META-INF/container.xml", container)
            archive.writestr("EPUB/package.opf", opf)
            archive.writestr("EPUB/nav.xhtml", nav)
            archive.writestr("EPUB/styles/main.css", css)
            for i, (heading, body) in enumerate(sections, 1):
                archive.writestr(f"EPUB/text/chapter-{i:03d}.xhtml", xhtml(heading, body, language))
        with zipfile.ZipFile(temporary) as archive:
            if archive.testzip() is not None:
                raise ValueError("EPUB archive integrity check failed")
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
