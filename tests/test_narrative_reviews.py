"""End-to-end tests for private, replayable editorial review decisions."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import narrative_intelligence as app
import narrative_reviews as reviews
import narrative_memory as memory
from manuscript_pipeline import ProjectError


class ReviewWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.fixtures = Path(__file__).resolve().parents[1] / "examples" / "narrative-intelligence"
        self.before = self.fixtures / "avant"
        self.after = self.fixtures / "apres"
        self.memory_a = self.fixtures / "memory-before.json"
        self.memory_b = self.fixtures / "memory-after.json"

    def audit_report(self):
        source = memory.read_memory(self.memory_a)
        source["events"][0]["source"]["quote"] = "This quote does not occur in the book."
        return memory.audit(self.before, source)

    def test_finding_identity_survives_minor_wording_but_evidence_must_match(self):
        report = reviews.attach(self.audit_report())
        issue = next(x for x in report["issues"] if x["code"] == "stale_source")
        previous = issue["review"]
        self.assertEqual(previous["status"], "open")
        choices = {previous["id"]: {
            "id": previous["id"], "fingerprint": previous["fingerprint"],
            "status": "confirmed", "note": "À corriger dans ma bible"
        }}
        second = reviews.attach(self.audit_report(), choices)
        second_issue = next(x for x in second["issues"] if x["code"] == "stale_source")
        self.assertEqual(second_issue["review"]["status"], "confirmed")
        self.assertFalse(second_issue["review"]["stale"])
        self.assertEqual(second["review_summary"]["confirmed"], 1)

        changed = self.audit_report()
        changed["issues"][0]["detail"] = "Une nouvelle description de l'anomalie"
        revised = reviews.attach(changed, choices)
        self.assertTrue(revised["issues"][0]["review"]["stale"])
        self.assertEqual(revised["issues"][0]["review"]["status"], "open")
        self.assertEqual(revised["review_summary"]["stale"], 1)

    def test_comment_is_html_escaped_and_report_is_fully_offline(self):
        report = reviews.attach(self.audit_report())
        candidate = report["issues"][0]["review"]
        entry = {candidate["id"]: {
            "id": candidate["id"], "fingerprint": candidate["fingerprint"],
            "status": "intentional", "note": "</textarea><script>alert('bad')</script>"
        }}
        shown = reviews.attach(self.audit_report(), entry)
        html = app.render_html(shown)
        self.assertNotIn("</textarea><script>alert", html)
        self.assertIn("&lt;script&gt;alert", html)
        self.assertIn("Exporter mes décisions", html)
        self.assertIn("application/json", html)
        self.assertNotIn("https://", html)

    def test_review_round_trip_with_real_cli_and_no_source_overwrite(self):
        a = self.base / "first.json"
        report = reviews.attach(memory.compare(self.before, self.after,
                                                memory.read_memory(self.memory_a),
                                                memory.read_memory(self.memory_b)))
        changed = report["consequences"][0]["review"]
        choices = {"format_version": 1, "items": [{
            "id": changed["id"], "fingerprint": changed["fingerprint"],
            "status": "needs_rewrite", "note": "Vérifier la traversée"
        }]}
        a.write_text(json.dumps(choices), encoding="utf-8")
        report_path = self.base / "report.json"
        html_path = self.base / "report.html"
        rc = app.cli(["compare", str(self.before), str(self.after),
                      str(self.memory_a), str(self.memory_b),
                      "--review-decisions", str(a),
                      "--json-out", str(report_path),
                      "--html-out", str(html_path)])
        self.assertEqual(rc, 0)
        result = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(result["review_summary"]["needs_rewrite"], 1)
        self.assertEqual(result["consequences"][0]["review"]["status"], "needs_rewrite")
        self.assertIn("Vérifier la traversée", html_path.read_text(encoding="utf-8"))
        self.assertEqual(app.cli(["audit", str(self.before), str(self.memory_a),
                                  "--review-decisions", str(a),
                                  "--html-out", str(a), "--force"]), 2)

    def test_reject_invalid_duplicate_and_oversize_reviews(self):
        cases = [
            {"format_version": 2, "items": []},
            {"format_version": 1, "items": [{"id": "issue:a", "status": "confirmed"}]},
            {"format_version": 1, "items": [{"id": "issue:a", "status": "evil", "fingerprint": "a"*64}]},
            {"format_version": 1, "items": [{"id": "issue:a", "status": "confirmed",
                                             "fingerprint": "a"*64, "note": "x" * 2001}]},
            {"format_version": 1, "items": [
                {"id": "issue:a", "status": "open", "fingerprint": "a"*64},
                {"id": "issue:a", "status": "open", "fingerprint": "b"*64}
            ]}
        ]
        file = self.base / "bad.json"
        for payload in cases:
            with self.subTest(payload=payload):
                file.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises(ProjectError):
                    reviews.read_decisions(file)

    def test_absent_findings_preserved_as_warnings_instead_of_silently_dropped(self):
        extra = {"issue:obsolete": {
            "id": "issue:obsolete", "fingerprint": "0"*64,
            "status": "intentional", "note": "Ancienne décision"
        }}
        report = reviews.attach(memory.audit(self.before, memory.read_memory(self.memory_a)), extra)
        self.assertEqual(report["review_warnings"][0]["id"], "issue:obsolete")


if __name__ == "__main__":
    unittest.main()
