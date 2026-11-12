"""Contract and regression tests for Narrative Intelligence v1 (fictional data only)."""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import narrative_memory as memory_engine
import narrative_intelligence as app
from manuscript_pipeline import ProjectError


def memory_document(updated=False, alternative=False):
    map_value = "destroyed" if updated else "usable"
    rope_value = "ready" if alternative else "absent"
    first = "Mira brûle la carte." if updated else "Mira trouve une carte."
    return {
        "schema_version": 1,
        "project": "Le Pont des Brumes (fiction)",
        "characters": [
            {"id": "mira", "name": "Mira", "aliases": ["La navigatrice"]},
            {"id": "noa", "name": "Noa", "aliases": []}
        ],
        "events": [
            {"id": "e1", "label": "Mira rencontre la carte", "time_index": 1,
             "participants": ["mira"], "precedes": ["e2"],
             "source": {"chapter": "sections/chapter_01.txt", "quote": first}},
            {"id": "e2", "label": "Mira traverse le pont", "time_index": 2,
             "participants": ["mira"], "precedes": ["e3"],
             "requires_knowledge": [{"character": "mira", "fact": "map"}],
             "source": {"chapter": "sections/chapter_02.txt", "quote": "Mira traverse le pont."}},
            {"id": "e3", "label": "Noa attend Mira", "time_index": 3,
             "participants": ["mira", "noa"],
             "source": {"chapter": "sections/chapter_03.txt",
                        "quote": "Noa attend Mira derrière le pont."}}
        ],
        "facts": [
            {"id": "map", "subject": "world", "attribute": "map_status",
             "value": map_value, "from_event": "e1", "confidence": "confirmed",
             "source": {"chapter": "sections/chapter_01.txt", "quote": first}},
            {"id": "rope", "subject": "world", "attribute": "rope_status",
             "value": rope_value, "confidence": "confirmed",
             "source": {"chapter": "sections/chapter_02.txt",
                        "quote": "Une corde pend près de l'eau."}}
        ],
        "knowledge": [
            {"id": "k_map", "character": "mira", "fact": "map", "state": "knows",
             "since_event": "e1",
             "source": {"chapter": "sections/chapter_01.txt", "quote": first}}
        ],
        "dependencies": [
            {"id": "d_bridge", "effect_event": "e2",
             "because_any": [["fact:map=usable"], ["fact:rope=ready"]],
             "source": {"chapter": "sections/chapter_02.txt", "quote": "Mira traverse le pont."}},
            {"id": "d_arrival", "effect_event": "e3",
             "because_any": [["event:e2"]],
             "source": {"chapter": "sections/chapter_03.txt",
                        "quote": "Noa attend Mira derrière le pont."}}
        ]
    }


class NarrativeIntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.old = base / "old"
        self.new = base / "new"
        self.old_memory = memory_document()
        self.new_memory = memory_document(updated=True)
        for root, changed in ((self.old, False), (self.new, True)):
            (root / "sections").mkdir(parents=True)
            project = {
                "format_version": 1, "title": "Le Pont des Brumes",
                "sections": [{"file": "sections/chapter_0" + str(i) + ".txt",
                              "heading": "Chapitre " + str(i)} for i in range(1, 4)]
            }
            (root / "project.json").write_text(json.dumps(project), encoding="utf-8")
            first = "Mira brûle la carte." if changed else "Mira trouve une carte."
            for index, paragraphs in ((1, first),
                                      (2, "Une corde pend près de l'eau.\n\nMira traverse le pont."),
                                      (3, "Noa attend Mira derrière le pont.")):
                (root / "sections" / ("chapter_0" + str(index) + ".txt")).write_text(
                    "Chapitre " + str(index) + "\n\n" + paragraphs + "\n", encoding="utf-8")

    def test_audit_has_sourced_timeline_and_knowledge(self):
        report = memory_engine.audit(self.old, self.old_memory)
        self.assertEqual(report["counts"]["events"], 3)
        self.assertEqual([e["id"] for e in report["timeline"]], ["e1", "e2", "e3"])
        self.assertEqual(report["causal_support"]["e3"]["state"], "supported")
        self.assertFalse([i for i in report["issues"] if i["severity"] == "review"])

    def test_distant_consequence_propagates_across_chapters(self):
        report = memory_engine.compare(self.old, self.new, self.old_memory, self.new_memory)
        effects = {x["event"]: x for x in report["consequences"]}
        self.assertEqual(effects["e2"]["status"], "declared_support_lost")
        self.assertEqual(effects["e3"]["status"], "declared_support_lost")
        self.assertGreater(report["changed_blocks"], 0)
        self.assertTrue(any(x["kind"] == "facts" and x["id"] == "map"
                            for x in report["memory_changes"]))
        self.assertNotIn("Noa attend Mira", json.dumps(report["before"]["issues"]))

    def test_alternative_justification_prevents_false_lost_support(self):
        revised = memory_document(updated=True, alternative=True)
        report = memory_engine.compare(self.old, self.new, self.old_memory, revised)
        effects = {x["event"]: x for x in report["consequences"]}
        self.assertEqual(effects["e2"]["after"], "supported")
        self.assertNotEqual(effects["e2"]["status"], "declared_support_lost")
        self.assertEqual(effects["e3"]["after"], "supported")

    def test_knowledge_before_acquisition_is_reviewed(self):
        revised = copy.deepcopy(self.old_memory)
        revised["knowledge"][0]["since_event"] = "e3"
        report = memory_engine.audit(self.old, revised)
        codes = {i["code"] for i in report["issues"]}
        self.assertIn("knowledge_not_yet_acquired", codes)

    def test_unknown_time_is_uncertain_not_a_fabricated_error(self):
        revised = copy.deepcopy(self.old_memory)
        revised["events"][0]["time_index"] = None
        revised["events"][0]["precedes"] = []
        report = memory_engine.audit(self.old, revised)
        self.assertTrue(any(i["code"] == "partial_chronology" for i in report["issues"]))
        self.assertIn(report["causal_support"]["e2"]["state"], ("uncertain", "unsupported"))

    def test_fact_collision_only_for_overlapping_confirmed_world_states(self):
        revised = copy.deepcopy(self.old_memory)
        revised["facts"].append({
            "id": "map_other", "subject": "world", "attribute": "map_status",
            "value": "missing", "from_event": "e1", "confidence": "confirmed",
            "source": revised["facts"][0]["source"]
        })
        report = memory_engine.audit(self.old, revised)
        self.assertIn("overlapping_world_facts", {i["code"] for i in report["issues"]})
        revised["facts"][-1]["confidence"] = "tentative"
        report = memory_engine.audit(self.old, revised)
        self.assertNotIn("overlapping_world_facts", {i["code"] for i in report["issues"]})

    def test_stale_quote_is_review_not_authoritative_truth(self):
        revised = copy.deepcopy(self.old_memory)
        revised["facts"][0]["source"]["quote"] = "Un dragon invisible est ici."
        report = memory_engine.audit(self.old, revised)
        self.assertTrue(any(i["code"] == "stale_source" for i in report["issues"]))

    def test_unverifiable_source_does_not_count_as_supported_causality(self):
        revised = copy.deepcopy(self.old_memory)
        revised["facts"][0]["source"]["quote"] = "Citation perdue du manuscrit."
        report = memory_engine.audit(self.old, revised)
        self.assertIn("stale_source", [i["code"] for i in report["issues"]])
        self.assertEqual(report["causal_support"]["e2"]["state"], "uncertain")
        self.assertEqual(report["causal_support"]["e3"]["state"], "uncertain")

    def test_reject_unknown_references_unsafe_sources_and_cycles(self):
        revised = copy.deepcopy(self.old_memory)
        revised["dependencies"][0]["because_any"] = [["fact:does_not_exist"]]
        with self.assertRaises(ProjectError):
            memory_engine.audit(self.old, revised)
        revised = copy.deepcopy(self.old_memory)
        revised["facts"][0]["source"]["chapter"] = "../secret.txt"
        with self.assertRaises(ProjectError):
            memory_engine.audit(self.old, revised)
        revised = copy.deepcopy(self.old_memory)
        revised["dependencies"][0]["because_any"][0].append("event:e1")
        revised["dependencies"].append({
            "id": "cycle", "effect_event": "e1",
            "because_any": [["event:e3"]],
            "source": revised["events"][0]["source"]
        })
        with self.assertRaises(ProjectError):
            memory_engine.audit(self.old, revised)

    def test_partial_order_precedes_even_when_event_time_is_unknown(self):
        revised = copy.deepcopy(self.old_memory)
        revised["events"][0]["time_index"] = None
        report = memory_engine.audit(self.old, revised)
        ordered = [item["id"] for item in report["timeline"]]
        self.assertLess(ordered.index("e1"), ordered.index("e2"))

    def test_public_demo_is_complete_and_reproducible(self):
        examples = Path(__file__).resolve().parents[1] / "examples" / "narrative-intelligence"
        before = memory_engine.read_memory(examples / "memory-before.json")
        after = memory_engine.read_memory(examples / "memory-after.json")
        report = memory_engine.compare(examples / "avant", examples / "apres", before, after)
        by_event = {item["event"]: item for item in report["consequences"]}
        self.assertEqual(by_event["e3"]["status"], "declared_support_lost")
        self.assertGreater(report["changed_blocks"], 0)

    def test_tentative_facts_cannot_certify_a_causal_justification(self):
        revised = copy.deepcopy(self.old_memory)
        revised["facts"][0]["confidence"] = "tentative"
        support = memory_engine.audit(self.old, revised)["causal_support"]
        self.assertEqual(support["e2"]["state"], "uncertain")
        self.assertEqual(support["e3"]["state"], "uncertain")

    def test_belief_is_not_knowledge_unless_explicitly_requested(self):
        revised = copy.deepcopy(self.old_memory)
        revised["dependencies"][0]["because_any"] = [["knowledge:k_map"]]
        revised["knowledge"][0]["state"] = "believes"
        first = memory_engine.audit(self.old, revised)
        self.assertEqual(first["causal_support"]["e2"]["state"], "unsupported")
        self.assertIn("knowledge_not_documented", [i["code"] for i in first["issues"]])
        revised["dependencies"][0]["because_any"] = [["knowledge:k_map=believes"]]
        second = memory_engine.audit(self.old, revised)
        self.assertEqual(second["causal_support"]["e2"]["state"], "supported")

    def test_explicit_precedes_resolves_undated_causal_relation(self):
        revised = copy.deepcopy(self.old_memory)
        for event in revised["events"]:
            event["time_index"] = None
        report = memory_engine.audit(self.old, revised)
        self.assertEqual(report["causal_support"]["e2"]["state"], "supported")
        self.assertEqual(report["causal_support"]["e3"]["state"], "supported")
        self.assertIn("partial_chronology", [issue["code"] for issue in report["issues"]])
        revised["events"][0]["precedes"] = []
        report = memory_engine.audit(self.old, revised)
        self.assertEqual(report["causal_support"]["e2"]["state"], "uncertain")

    def test_html_escapes_personal_text_and_is_standalone(self):
        revised = copy.deepcopy(self.old_memory)
        revised["characters"][0]["name"] = "<img src=x onerror=alert(1)>"
        html = app.render_html(memory_engine.audit(self.old, revised))
        self.assertNotIn("<img src=x", html)
        self.assertIn("&lt;img src=x", html)
        self.assertNotIn("https://", html)
        self.assertIn("Chronologie annotée", html)
        self.assertIn("type='search'", html)

    def test_output_protection_and_cli_artifacts(self):
        base = Path(self.temp.name)
        old_json = base / "old-memory.json"
        new_json = base / "new-memory.json"
        old_json.write_text(json.dumps(self.old_memory), encoding="utf-8")
        new_json.write_text(json.dumps(self.new_memory), encoding="utf-8")
        json_out = base / "report.json"
        html_out = base / "report.html"
        rc = app.cli(["compare", str(self.old), str(self.new), str(old_json), str(new_json),
                      "--json-out", str(json_out), "--html-out", str(html_out)])
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(json_out.read_text(encoding="utf-8"))["kind"],
                         "narrative_comparison")
        self.assertIn("<!doctype html>", html_out.read_text(encoding="utf-8"))
        self.assertEqual(app.cli(["compare", str(self.old), str(self.new),
                                  str(old_json), str(new_json),
                                  "--json-out", str(json_out)]), 2)
        forbidden = self.old / "sections" / "chapter_01.txt"
        before = forbidden.read_text(encoding="utf-8")
        self.assertEqual(app.cli(["audit", str(self.old), str(old_json),
                                  "--html-out", str(forbidden), "--force"]), 2)
        self.assertEqual(forbidden.read_text(encoding="utf-8"), before)

    def test_cli_audit_and_errors(self):
        base = Path(self.temp.name)
        src = base / "memory.json"
        src.write_text(json.dumps(self.old_memory), encoding="utf-8")
        self.assertEqual(app.cli(["audit", str(self.old), str(src),
                                  "--json-out", str(base / "a.json")]), 0)
        src.write_text('{"schema_version": 99}', encoding="utf-8")
        self.assertEqual(app.cli(["audit", str(self.old), str(src)]), 2)


if __name__ == "__main__":
    unittest.main()
