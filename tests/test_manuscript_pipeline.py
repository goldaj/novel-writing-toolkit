"""Regression tests for the generic manuscript pipeline; no private manuscripts required."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import manuscript_pipeline as pipeline


class ManuscriptWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "novel"
        pipeline.initialize(self.root, 3, "Histoire fictive")
        self.config = self.root / "project.json"

    def set_chapter(self, index, body):
        (self.root / "sections" / f"chapter_{index:02d}.txt").write_text(
            f"Chapitre {index}\n\n{body}\n", encoding="utf-8"
        )

    def update_config(self, **values):
        obj = json.loads(self.config.read_text(encoding="utf-8"))
        obj.update(values)
        self.config.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")

    def test_init_and_build(self):
        self.set_chapter(1, "Je marche vers la vallée.")
        self.set_chapter(2, "Je retrouve la lumière.")
        self.set_chapter(3, "Nous rentrons ensemble.")
        self.assertEqual(pipeline.cli(["check", str(self.root)]), 0)
        self.assertEqual(pipeline.cli(["build", str(self.root)]), 0)
        manuscript = (self.root / "manuscript.txt").read_text(encoding="utf-8")
        self.assertLess(manuscript.index("Chapitre 1"), manuscript.index("Chapitre 2"))
        self.assertLess(manuscript.index("Chapitre 2"), manuscript.index("Chapitre 3"))
        report = json.loads((self.root / "manuscript-report.json").read_text(encoding="utf-8"))
        self.assertTrue(report["passed"])
        self.assertEqual(report["section_count"], 3)
        self.assertEqual(report["total_words"], pipeline.count_words(manuscript))
        self.assertEqual(report["sha256"], __import__("hashlib").sha256(manuscript.encode()).hexdigest())

    def test_mismatched_heading_blocks_output(self):
        (self.root / "sections" / "chapter_02.txt").write_text(
            "Deuxième chapitre\n\nTexte.\n", encoding="utf-8"
        )
        self.assertEqual(pipeline.cli(["build", str(self.root)]), 1)
        self.assertFalse((self.root / "manuscript.txt").exists())
        report, _, _ = pipeline.inspect(self.root)
        self.assertIn("heading_mismatch", [x["code"] for x in report["issues"]])

    def test_textual_requirements_and_limits(self):
        self.set_chapter(1, "La vie est douce.")
        self.update_config(minimum_words=100, required_phrases=["lune bleue"],
                           forbidden_phrases=["vie est"])
        report, _, _ = pipeline.inspect(self.root)
        codes = {issue["code"] for issue in report["issues"]}
        self.assertEqual(codes, {"below_minimum_words", "required_phrase_missing", "forbidden_phrase"})

    def test_traversal_and_duplicate_sections_rejected(self):
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["sections"][0]["file"] = "../../secret.txt"
        self.update_config(sections=config["sections"])
        with self.assertRaises(pipeline.ProjectError):
            pipeline.inspect(self.root)
        config["sections"][0]["file"] = "sections/chapter_01.txt"
        config["sections"][1]["file"] = "sections/chapter_01.txt"
        self.update_config(sections=config["sections"])
        with self.assertRaises(pipeline.ProjectError):
            pipeline.inspect(self.root)

    def test_reject_overwrite_without_force(self):
        self.assertEqual(pipeline.cli(["build", str(self.root)]), 0)
        self.assertEqual(pipeline.cli(["build", str(self.root)]), 2)
        self.assertEqual(pipeline.cli(["build", str(self.root), "--force"]), 0)

    def test_output_path_cannot_overwrite_source(self):
        self.assertEqual(pipeline.cli(
            ["build", str(self.root), "--output", "sections/chapter_01.txt"]
        ), 2)
        self.assertEqual(pipeline.cli(
            ["build", str(self.root), "--output", "manuscript-report.json",
             "--report", "manuscript-report.json"]
        ), 2)

    def test_repeated_paragraph_warning_does_not_fail(self):
        text = "Une longue phrase volontairement répétée pour vérifier que le moteur peut signaler des paragraphes réemployés dans plusieurs chapitres."
        self.set_chapter(1, text)
        self.set_chapter(2, text)
        report, _, _ = pipeline.inspect(self.root)
        self.assertTrue(report["passed"])
        self.assertIn("repeated_long_paragraph", [w["code"] for w in report["warnings"]])

    def test_unreadable_section_reports_issue(self):
        (self.root / "sections" / "chapter_03.txt").unlink()
        report, _, _ = pipeline.inspect(self.root)
        self.assertFalse(report["passed"])
        self.assertEqual(report["readable_sections"], 2)
        self.assertIn("unreadable_section", [e["code"] for e in report["issues"]])

    def test_init_refuses_existing_files(self):
        with self.assertRaises(pipeline.ProjectError):
            pipeline.initialize(self.root, 3, "Encore")

    def test_boolean_word_limit_is_not_valid(self):
        self.update_config(minimum_words=True)
        with self.assertRaises(pipeline.ProjectError):
            pipeline.inspect(self.root)

    def test_unicode_and_bom_accepted(self):
        (self.root / "sections" / "chapter_01.txt").write_bytes(
            "\ufeffChapitre 1\r\n\r\nL’été s’éveille.\r\n".encode("utf-8")
        )
        report, output, _ = pipeline.inspect(self.root)
        self.assertTrue(report["passed"])
        self.assertIn("L’été s’éveille.", output)
        self.assertNotIn("\r", output)


if __name__ == "__main__":
    unittest.main()
