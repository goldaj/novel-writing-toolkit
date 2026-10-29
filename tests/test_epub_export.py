"""Offline synthetic EPUB 3 tests. Never touch a real manuscript."""
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from manuscript_pipeline import cli, initialize

NS = {
    "opf": "http://www.idpf.org/2007/opf",
    "x": "http://www.w3.org/1999/xhtml",
    "dc": "http://purl.org/dc/elements/1.1/",
}


class EpubTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name) / "novel"
        initialize(self.root, 3, "Histoire & <test>")
        for number in range(1, 4):
            content = f"Chapitre {number}\n\nUn rêve & un renard < libre >.\n\n## Scène\n\nL'été continue."
            (self.root / "sections" / f"chapter_{number:02d}.txt").write_text(content, encoding="utf-8")

    def call(self, *opts):
        return cli(["epub", str(self.root), *opts])

    def test_generates_valid_epub_with_toc_and_ordered_spine(self):
        self.assertEqual(self.call("--author", "Écrivaine & ami"), 0)
        target = self.root / "manuscript.epub"
        self.assertTrue(target.exists())
        with zipfile.ZipFile(target) as z:
            self.assertIsNone(z.testzip())
            self.assertEqual(z.namelist()[0], "mimetype")
            self.assertEqual(z.getinfo("mimetype").compress_type, zipfile.ZIP_STORED)
            self.assertEqual(z.read("mimetype"), b"application/epub+zip")
            self.assertEqual(len(z.namelist()), 8)
            container = ET.fromstring(z.read("META-INF/container.xml"))
            self.assertTrue(any(e.attrib.get("full-path") == "EPUB/package.opf" for e in container.iter()))
            package = ET.fromstring(z.read("EPUB/package.opf"))
            self.assertEqual(package.find(".//dc:title", NS).text, "Histoire & <test>")
            self.assertEqual(package.find(".//dc:creator", NS).text, "Écrivaine & ami")
            refs = package.findall(".//opf:spine/opf:itemref", NS)
            self.assertEqual([e.attrib["idref"] for e in refs], ["chapter-1", "chapter-2", "chapter-3"])
            manifest = package.findall(".//opf:manifest/opf:item", NS)
            self.assertTrue(any(e.attrib.get("properties") == "nav" for e in manifest))
            nav = ET.fromstring(z.read("EPUB/nav.xhtml"))
            names = [x.text for x in nav.findall(".//x:li/x:a", NS)]
            self.assertEqual(names, ["Chapitre 1", "Chapitre 2", "Chapitre 3"])
            ch1 = z.read("EPUB/text/chapter-001.xhtml")
            page = ET.fromstring(ch1)
            self.assertEqual(page.find(".//x:h2", NS).text, "Chapitre 1")
            self.assertIn(b"&amp;", ch1)
            self.assertIn(b"&lt;", ch1)
            self.assertNotIn(b"< libre >", ch1)
            self.assertEqual(len(page.findall(".//x:h3", NS)), 1)
            for number in range(1, 4):
                ET.fromstring(z.read(f"EPUB/text/chapter-{number:03d}.xhtml"))

    def test_export_respects_existing_files_and_force(self):
        self.assertEqual(self.call(), 0)
        dest = self.root / "manuscript.epub"
        before = dest.read_bytes()
        self.assertEqual(self.call(), 2)
        self.assertEqual(dest.read_bytes(), before)
        self.assertEqual(self.call("--force"), 0)

    def test_cannot_overwrite_sources_or_escape_project(self):
        for output in ("sections/chapter_01.txt", "project.json", "../escape.epub"):
            self.assertEqual(self.call("--output", output), 2)
            self.assertFalse((self.root / "manuscript.epub").exists())

    def test_qa_rejection_prevents_partial_output(self):
        invalid = self.root / "sections/chapter_01.txt"
        invalid.write_text("Wrong heading\n\nText", encoding="utf-8")
        self.assertEqual(self.call(), 1)
        self.assertFalse((self.root / "manuscript.epub").exists())

    def test_reject_illegal_xml_unicode_without_output(self):
        bad = self.root / "sections/chapter_01.txt"
        bad.write_text("Chapitre 1\n\nHidden control:\x01", encoding="utf-8")
        self.assertEqual(self.call(), 2)
        self.assertFalse((self.root / "manuscript.epub").exists())

    def test_metadata_validation_and_json_report(self):
        self.assertEqual(self.call("--language", "../en"), 2)
        self.assertEqual(self.call("--language", "fr-FR", "--json"), 0)
        with zipfile.ZipFile(self.root / "manuscript.epub") as z:
            package = ET.fromstring(z.read("EPUB/package.opf"))
            self.assertEqual(package.find(".//dc:language", NS).text, "fr-FR")
        self.assertFalse((self.root / "manuscript-report.json").exists())


if __name__ == "__main__":
    unittest.main()
