"""Local narrative assistant: no network in tests; mock responses and source checks."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import narrative_local_assist as assist
from manuscript_pipeline import ProjectError


class LocalAssistanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "novel"
        (self.root / "sections").mkdir(parents=True)
        self.chapter = self.root / "sections" / "01.txt"
        self.chapter.write_text("Chapitre 1\nMira ferme la porte.\n\n"
                                "Noa garde la clé dans sa poche.\n", encoding="utf-8")
        (self.root / "project.json").write_text(json.dumps({
            "format_version": 1, "title": "Roman entièrement fictif",
            "sections": [{"file": "sections/01.txt", "heading": "Chapitre 1"}]
        }), encoding="utf-8")
        self.endpoint = "http://127.0.0.1:11434/api/generate"

    def test_opening_paragraph_without_blank_separator_is_retained(self):
        blocks = assist.segments(self.root)
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0]["content"], "Mira ferme la porte.")
        self.assertEqual(blocks[1]["content"], "Noa garde la clé dans sa poche.")

    def test_reject_external_endpoint_proxy_or_missing_explicit_consent(self):
        for endpoint in (
            "http://example.org:11434/api/generate",
            "https://127.0.0.1:11434/api/generate",
            "http://127.0.0.1:11434/api/chat",
            "http://127.0.0.1:11434/api/generate?token=abc",
            "http://127.0.0.1:11434@evil.example/api/generate"
        ):
            with self.subTest(endpoint=endpoint), self.assertRaises(ProjectError):
                assist.endpoint_check(endpoint)
        out = Path(self.tmp.name) / "candidates.json"
        self.assertEqual(assist.main([str(self.root), "--model", "local-model",
                                      "--out", str(out)]), 2)
        self.assertFalse(out.exists())

    def test_verified_quote_is_candidate_and_hallucinated_quote_is_rejected(self):
        def response(model, text, endpoint, timeout):
            return {"claims": [
                {"kind": "event", "subject": "Mira", "statement": "Mira ferme la porte.",
                 "quote": "Mira ferme la porte."},
                {"kind": "event", "subject": "Mira", "statement": "Mira quitte la ville.",
                 "quote": "Mira quitte la ville."}
            ]}
        result = assist.extract(self.root, "local-model", self.endpoint, max_blocks=1,
                                query=response)
        self.assertEqual(result["processed_blocks"], 1)
        self.assertEqual(len(result["candidates"]), 1)
        self.assertEqual(result["rejected_claims"], 1)
        self.assertEqual(result["candidates"][0]["status"], "pending_author_review")
        self.assertEqual(result["candidates"][0]["trust"], "hypothesis")
        self.assertEqual(result["candidates"][0]["source"]["chapter"], "sections/01.txt")
        self.assertTrue(result["truncated"])
        self.assertEqual(result["next_block"], 1)

    def test_malformed_model_output_does_not_make_fake_fact(self):
        def bad(*args):
            return {"claims": [{"kind": "fact", "subject": "Mira", "statement": "Quelque chose"}]}
        result = assist.extract(self.root, "local-model", self.endpoint, max_blocks=1, query=bad)
        self.assertEqual(result["candidates"], [])
        self.assertEqual(result["rejected_claims"], 1)
        with self.assertRaises(ProjectError):
            assist.extract(self.root, "local-model", self.endpoint, max_blocks=1,
                           query=lambda *args: {"claims": [{}] * 13})

    def test_cli_optin_generates_private_report_without_touching_manuscript(self):
        outfile = Path(self.tmp.name) / "candidates.json"
        before = self.chapter.read_bytes()
        fake_response = {"claims": [
            {"kind": "event", "subject": "Noa", "statement": "Noa garde une clé",
             "quote": "Noa garde la clé dans sa poche."}
        ]}
        with patch.object(assist, "ollama_generate", return_value=fake_response) as mock:
            self.assertEqual(assist.main([str(self.root), "--model", "safe-local",
                                          "--allow-local-model", "--out", str(outfile)]), 0)
            self.assertEqual(mock.call_count, 2)
        results = json.loads(outfile.read_text(encoding="utf-8"))
        self.assertEqual(results["format_version"], 1)
        self.assertEqual(len(results["candidates"]), 1)
        self.assertEqual(self.chapter.read_bytes(), before)
        with patch.object(assist, "ollama_generate", return_value=fake_response):
            self.assertEqual(assist.main([str(self.root), "--model", "safe-local",
                                          "--allow-local-model",
                                          "--out", str(self.chapter), "--force"]), 2)
        self.assertEqual(self.chapter.read_bytes(), before)

    def test_bounded_work_and_invalid_model(self):
        with self.assertRaises(ProjectError):
            assist.extract(self.root, "invalid model", self.endpoint,
                           query=lambda *args: {"claims": []})
        with self.assertRaises(ProjectError):
            assist.extract(self.root, "local-model", self.endpoint, start=1000,
                           query=lambda *args: {"claims": []})
        with self.assertRaises(ProjectError):
            assist.extract(self.root, "local-model", self.endpoint, max_blocks=501,
                           query=lambda *args: {"claims": []})


if __name__ == "__main__":
    unittest.main()
