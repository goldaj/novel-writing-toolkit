"""End-to-end fictional tests for explicit human promotion of local AI suggestions."""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from manuscript_pipeline import ProjectError
import narrative_curator as curator
import narrative_local_assist as assist
import narrative_memory as memory


class NarrativeCurationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.project = self.base / "book"
        (self.project / "sections").mkdir(parents=True)
        self.chapter = self.project / "sections" / "chapter_01.txt"
        self.chapter.write_text("Chapitre 1\n\nMira trouve une clé.\n\n"
                                "Mira ouvre la porte.\n", encoding="utf-8")
        (self.project / "project.json").write_text(json.dumps({
            "format_version": 1, "title": "Un essai purement fictif",
            "sections": [{"file": "sections/chapter_01.txt", "heading": "Chapitre 1"}]
        }), encoding="utf-8")
        self.before = {
            "schema_version": 1, "project": "Un essai purement fictif",
            "characters": [{"id": "mira", "name": "Mira"}],
            "events": [
                {"id": "E1", "label": "Trouver la clé", "time_index": 1,
                 "precedes": ["E2"], "source": {"chapter": "sections/chapter_01.txt",
                                               "quote": "Mira trouve une clé."}},
                {"id": "E2", "label": "Ouvrir la porte", "time_index": 2,
                 "source": {"chapter": "sections/chapter_01.txt",
                            "quote": "Mira ouvre la porte."}}
            ], "facts": [], "knowledge": [], "dependencies": []
        }

        def local_stub(_model, text, _endpoint, _timeout):
            if "trouve une clé" in text:
                return {"claims": [
                    {"kind": "fact", "subject": "clé", "statement": "La clé est utilisable",
                     "quote": "Mira trouve une clé."},
                    {"kind": "knowledge", "subject": "Mira",
                     "statement": "Mira connaît l'existence de la clé",
                     "quote": "Mira trouve une clé."}
                ]}
            return {"claims": [
                {"kind": "causal_link", "subject": "porte",
                 "statement": "La clé permet d'ouvrir la porte",
                 "quote": "Mira ouvre la porte."}
            ]}
        self.batch = assist.extract(
            self.project, "local-fiction", "http://127.0.0.1:11434/api/generate",
            query=local_stub)
        self.kind_ids = {item["kind"]: item["id"] for item in self.batch["candidates"]}
        self.accept = {
            "fact": {"id": "key", "subject": "world",
                     "attribute": "key_status", "value": "usable", "from_event": "E1"},
            "knowledge": {"id": "K1", "character": "mira", "fact": "key",
                          "state": "knows", "since_event": "E1"},
            "causal_link": {"id": "D1", "effect_event": "E2",
                            "because_any": [["fact:key=usable", "knowledge:K1"]]}
        }
        self.decisions = {"format_version": 1, "items": [
            {"id": item["id"], "action": "accept",
             "annotation": copy.deepcopy(self.accept[item["kind"]])}
            for item in self.batch["candidates"]
        ]}

    def test_default_deny_template_does_not_promote_any_claim(self):
        raw = curator.template(self.batch)
        self.assertEqual([x["action"] for x in raw["items"]], ["skip"] * 3)
        result, stats = curator.promote(self.project, self.before, self.batch, raw)
        self.assertEqual(stats["accepted"], 0)
        self.assertEqual(len(result["dependencies"]), 0)
        self.assertEqual(len(result["facts"]), 0)
        self.assertEqual(len(result["curation_history"]), 1)

    def test_full_author_acceptance_produces_causal_memory_with_provenance(self):
        original = copy.deepcopy(self.before)
        result, stats = curator.promote(self.project, self.before,
                                        self.batch, self.decisions)
        self.assertEqual(stats["accepted"], 3)
        self.assertEqual(result["facts"][0]["id"], "key")
        self.assertEqual(result["knowledge"][0]["state"], "knows")
        self.assertEqual(result["dependencies"][0]["because_any"],
                         [["fact:key=usable", "knowledge:K1"]])
        self.assertEqual(result["facts"][0]["curation"]["origin"],
                         "human_accepted_local_candidate")
        report = memory.audit(self.project, result)
        self.assertEqual(report["causal_support"]["E2"]["state"], "supported")
        self.assertEqual(self.before, original)

    def test_tampered_block_hash_and_stale_manuscript_are_rejected(self):
        broken = copy.deepcopy(self.batch)
        broken["candidates"][0]["source"]["sha256"] = "0" * 64
        with self.assertRaises(ProjectError):
            curator.promote(self.project, self.before, broken, self.decisions)
        self.chapter.write_text("Chapitre 1\n\nMira perd la clé.\n\n"
                                "Mira ouvre la porte.\n", encoding="utf-8")
        with self.assertRaises(ProjectError):
            curator.promote(self.project, self.before, self.batch, self.decisions)

    def test_unapproved_or_unknown_or_duplicate_decisions_refused(self):
        decisions = copy.deepcopy(self.decisions)
        decisions["items"][0]["id"] = "C_invalid"
        with self.assertRaises(ProjectError):
            curator.promote(self.project, self.before, self.batch, decisions)
        decisions = copy.deepcopy(self.decisions)
        decisions["items"].append(copy.deepcopy(decisions["items"][0]))
        with self.assertRaises(ProjectError):
            curator.promote(self.project, self.before, self.batch, decisions)
        decisions = copy.deepcopy(self.decisions)
        decisions["items"][0]["action"] = "reject"
        with self.assertRaises(ProjectError):
            curator.promote(self.project, self.before, self.batch, decisions)

    def test_author_cannot_override_cited_source_or_bypass_schema(self):
        decisions = copy.deepcopy(self.decisions)
        decisions["items"][0]["annotation"]["source"] = {
            "chapter": "../secret.txt", "quote": "fake"
        }
        with self.assertRaises(ProjectError):
            curator.promote(self.project, self.before, self.batch, decisions)
        decisions = copy.deepcopy(self.decisions)
        decisions["items"][-1]["annotation"]["because_any"] = [["fact:unknown"]]
        with self.assertRaises(ProjectError):
            curator.promote(self.project, self.before, self.batch, decisions)

    def test_cli_round_trip_template_then_apply_without_overwrites(self):
        baseline = self.base / "baseline.json"
        candidates = self.base / "candidates.json"
        decisions = self.base / "decisions.json"
        new_memory = self.base / "memory-reviewed.json"
        baseline.write_text(json.dumps(self.before), encoding="utf-8")
        candidates.write_text(json.dumps(self.batch), encoding="utf-8")
        before_bytes = self.chapter.read_bytes()
        self.assertEqual(curator.cli(["template", str(candidates),
                                      "--out", str(decisions)]), 0)
        generated = json.loads(decisions.read_text(encoding="utf-8"))
        self.assertTrue(all(x["action"] == "skip" for x in generated["items"]))
        decisions.write_text(json.dumps(self.decisions), encoding="utf-8")
        self.assertEqual(curator.cli(["apply", str(self.project), str(baseline),
                                      str(candidates), str(decisions),
                                      "--out", str(new_memory)]), 0)
        self.assertEqual(memory.audit(self.project, curator.load(new_memory))[
                             "counts"]["dependencies"], 1)
        self.assertEqual(self.chapter.read_bytes(), before_bytes)
        self.assertEqual(curator.cli(["apply", str(self.project), str(baseline),
                                      str(candidates), str(decisions),
                                      "--out", str(new_memory)]), 2)
        self.assertEqual(curator.cli(["apply", str(self.project), str(baseline),
                                      str(candidates), str(decisions),
                                      "--out", str(self.chapter), "--force"]), 2)
        self.assertEqual(self.chapter.read_bytes(), before_bytes)


if __name__ == "__main__":
    unittest.main()
