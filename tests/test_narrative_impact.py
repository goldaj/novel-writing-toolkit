"""Synthetic narrative impact scenarios; no personal manuscript."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import manuscript_pipeline as pipeline
import narrative_impact as ni

DOSSIER = {
    "format_version": 1, "aliases": ["Léo"],
    "facts": [
        {"id": "taille", "label": "Taille de Léo", "before": "petit", "after": "grand"},
        {"id": "constitution", "before": "chétif", "after": "chétif"},
        {"id": "yeux", "before": "verts", "after": "bleus"},
    ],
    "rules": [
        {"id": "brimades", "label": "Brimades", "evidence_terms": ["brimad", "maltrait"],
         "because_any": [
             [{"fact": "taille", "equals": "petit"}],
             [{"fact": "constitution", "equals": "chétif"}]
         ]},
        {"id": "fuite", "label": "Fuite", "evidence_terms": ["fui", "fuir"],
         "because_any": [[{"rule": "brimades"}]]},
    ],
}


class NarrativeImpactTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.old, self.new = self.base / "before", self.base / "after"
        for folder in (self.old, self.new):
            pipeline.initialize(folder, 3, "Fiction synthétique")
        self.write(self.old, 1, "Léo était petit, chétif, avec les yeux verts.")
        self.write(self.new, 1, "Léo était grand, chétif, avec les yeux bleus.")
        self.write(self.old, 2, "Il subissait des brimades à l'école.")
        self.write(self.new, 2, "Il subissait des brimades à l'école.")
        self.write(self.old, 3, "Cent pages plus tard, Léo avait fui sa ville.")
        self.write(self.new, 3, "Cent pages plus tard, Léo avait fui sa ville.")

    def write(self, root, number, text):
        path = root / "sections" / f"chapter_{number:02}.txt"
        path.write_text(f"Chapitre {number}\n\n{text}\n", encoding="utf-8")

    def test_same_event_rejustified_by_frailty_and_eyes_unlinked(self):
        report = ni.analyze(self.old, self.new, DOSSIER)
        self.assertEqual(report["changed_blocks"], 1)
        items = {item["id"]: item for item in report["impact"]}
        self.assertEqual(items["yeux"]["status"], "no_declared_dependency")
        self.assertEqual(items["brimades"]["status"], "alternative_justification")
        self.assertEqual(items["fuite"]["status"], "support_preserved")
        self.assertEqual(items["brimades"]["new_evidence"][0]["chapter"], "sections/chapter_02.txt")
        self.assertEqual(items["fuite"]["new_evidence"][0]["chapter"], "sections/chapter_03.txt")

    def test_justification_lost_propagates_to_distant_chapters(self):
        lost = json.loads(json.dumps(DOSSIER))
        lost["facts"][1]["after"] = "robuste"
        report = ni.analyze(self.old, self.new, lost)
        rules = {item["id"]: item for item in report["impact"] if item["kind"] == "causal_rule"}
        self.assertEqual(rules["brimades"]["status"], "justification_lost_with_remaining_scene")
        self.assertEqual(rules["fuite"]["status"], "justification_lost_with_remaining_scene")
        self.assertEqual(rules["fuite"]["new_evidence"][0]["chapter"], "sections/chapter_03.txt")

    def test_unlinked_change_never_called_proven_harmless(self):
        report = ni.analyze(self.old, self.new)
        self.assertEqual(report["mode"], "retrieval_only")
        self.assertEqual(report["impact"], [])
        self.assertEqual(report["changed_blocks"], 1)
        self.assertTrue(report["changes"][0]["distant_candidates"])
        self.assertIn("not a proof", report["disclaimer"])

    def test_deletion_and_new_chapter_are_reported(self):
        self.write(self.new, 2, "Toute l'école était silencieuse.")
        a = ni.analyze(self.old, self.new)
        self.assertEqual(a["changed_blocks"], 2)
        self.assertEqual(a["changes"][1]["chapter"], "sections/chapter_02.txt")

    def test_html_escapes_untrusted_matter(self):
        self.write(self.new, 1, "<script>alert('bad')</script>")
        r = ni.analyze(self.old, self.new)
        markup = ni.render_html(r)
        self.assertNotIn("<script>", markup)
        self.assertIn("&lt;script&gt;", markup)

    def test_missing_rule_and_cycles_rejected(self):
        spec = json.loads(json.dumps(DOSSIER))
        spec["rules"][1]["because_any"] = [[{"rule": "brimades"}]]
        spec["rules"][0]["because_any"] = [[{"rule": "fuite"}]]
        with self.assertRaisesRegex(ni.ProjectError, "cycle"):
            ni.analyze(self.old, self.new, spec)
        spec["rules"][0]["because_any"] = [[{"rule": "nimportequoi"}]]
        with self.assertRaisesRegex(ni.ProjectError, "Unknown rule"):
            ni.analyze(self.old, self.new, spec)

    def test_invalid_dossier_does_not_make_authoritative_findings(self):
        with self.assertRaises(ni.ProjectError):
            ni.analyze(self.old, self.new, {"format_version": 2, "facts": []})
        with self.assertRaises(ni.ProjectError):
            ni.analyze(self.old, self.new, {"format_version": 1, "facts": [{"id":"x","before":"a"}]})
        with self.assertRaises(ni.ProjectError):
            ni.analyze(self.old, self.new, {"format_version": 1, "facts": [{"id":"x","before":"a","after":"b"}], "rules": [{"id":"x","because_any":[[{"fact":"x","equals":"a"}]]}]})

    def test_refuse_overwriting_story_even_with_force(self):
        chapter = self.new / "sections" / "chapter_01.txt"
        original = chapter.read_text(encoding="utf-8")
        result = ni.cli([str(self.old), str(self.new), "--force",
                         "--json-out", str(chapter)])
        self.assertEqual(result, 2)
        self.assertEqual(chapter.read_text(encoding="utf-8"), original)

    def test_cli_safe_outputs_and_readable_reports(self):
        dossier_path = self.base / "causes.json"
        dossier_path.write_text(json.dumps(DOSSIER, ensure_ascii=False), encoding="utf-8")
        report_path, html_path = self.base / "report.json", self.base / "report.html"
        args = [str(self.old),str(self.new),"--dossier",str(dossier_path),
                "--json-out",str(report_path),"--html-out",str(html_path)]
        self.assertEqual(ni.cli(args), 0)
        self.assertEqual(ni.cli(args), 2)
        self.assertEqual(ni.cli(args + ["--force"]), 0)
        doc = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(doc["changed_blocks"], 1)
        self.assertIn("Brimades", html_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
