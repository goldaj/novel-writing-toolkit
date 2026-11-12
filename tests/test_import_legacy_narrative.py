"""Synthetic tests for conservative legacy migration; no private story content."""
from __future__ import annotations
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import import_legacy_narrative as bridge
import narrative_memory as engine
from manuscript_pipeline import ProjectError


class LegacyImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "manuscript_work"
        (self.root / "draft").mkdir(parents=True)
        (self.root / "draft" / "prologue.txt").write_text(
            "Prologue\n\nLa gardienne lit une inscription.\n", encoding="utf-8")
        (self.root / "project.json").write_text(json.dumps({
            "format_version": 1, "title": "Exemple fictif",
            "sections": [{"file": "draft/prologue.txt", "heading": "Prologue"}]
        }), encoding="utf-8")
        self.evidence = {"path": "manuscript_work/draft/prologue.txt",
                         "line": 3, "needle": "La gardienne lit une inscription."}
        self.chrono = {"schema_version": 1, "title": "Exemple fictif",
                       "events": [{"id": "EV_01", "description": "Découverte d'une inscription",
                                   "when": "Il y a longtemps", "sequence": 0,
                                   "evidence": self.evidence}]}
        self.knowledge = {"schema_version": 1,
                          "entries": [{"id": "K_01", "knower": "La gardienne",
                                       "topic": "Inscription", "status": "Elle a lu la pierre",
                                       "anchor_id": "EV_01", "evidence": self.evidence}]}
        self.relations = {"format_version": 1,
                          "manual_facts": [{"id": "C_01", "label": "Point de canon",
                                            "evidence": self.evidence}],
                          "rules": [{"id": "D_01", "because_any": [["EV_01"]]}]}

    def test_import_is_valid_and_does_not_invent_fictional_time_or_truth(self):
        result = bridge.convert(self.root, self.chrono, self.knowledge, self.relations)
        self.assertEqual(result["events"][0]["time_index"], None)
        self.assertEqual(result["knowledge"][0]["state"], "suspects")
        self.assertNotIn("since_event", result["knowledge"][0])
        self.assertEqual(result["migration"]["causal_rules_require_review"], 1)
        self.assertEqual(len(result["dependencies"]), 0)
        report = engine.audit(self.root, result)
        self.assertEqual(report["counts"]["events"], 1)
        self.assertEqual(report["counts"]["knowledge"], 1)
        self.assertIn("partial_chronology", [x["code"] for x in report["issues"]])
        self.assertNotIn("stale_source", [x["code"] for x in report["issues"]])

    def test_rejects_undeclared_source_and_duplicate_events(self):
        altered = copy.deepcopy(self.chrono)
        altered["events"][0]["evidence"]["path"] = "../private.txt"
        with self.assertRaises(ProjectError):
            bridge.convert(self.root, altered)
        altered = copy.deepcopy(self.chrono)
        altered["events"].append(copy.deepcopy(altered["events"][0]))
        with self.assertRaises(ProjectError):
            bridge.convert(self.root, altered)

    def test_cli_keeps_sources_unchanged(self):
        work = Path(self.tmp.name)
        chronology = work / "chronology.json"
        knowledge = work / "knowledge.json"
        relations = work / "relations.json"
        for path, data in ((chronology, self.chrono), (knowledge, self.knowledge),
                           (relations, self.relations)):
            path.write_text(json.dumps(data), encoding="utf-8")
        output = work / "migration.json"
        before = (self.root / "draft" / "prologue.txt").read_bytes()
        self.assertEqual(bridge.cli([str(self.root), str(chronology),
                                     "--knowledge", str(knowledge),
                                     "--relations", str(relations),
                                     "--out", str(output)]), 0)
        self.assertEqual(engine.audit(self.root, bridge.load_json(output))["counts"]["events"], 1)
        self.assertEqual((self.root / "draft" / "prologue.txt").read_bytes(), before)
        self.assertEqual(bridge.cli([str(self.root), str(chronology),
                                     "--out", str(output)]), 2)
        self.assertEqual(bridge.cli([str(self.root), str(chronology),
                                     "--out", str(self.root / "draft" / "prologue.txt"),
                                     "--force"]), 2)


if __name__ == "__main__":
    unittest.main()
