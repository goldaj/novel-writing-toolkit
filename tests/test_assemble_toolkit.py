"""Portable manuscript assembly with synthetic chapters only."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.assemble_manuscript import SECTION_FILES, EXPECTED_HEADINGS

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "assemble_manuscript.py"


class ManuscriptToolkitTests(unittest.TestCase):
    def test_generic_output_and_manifest_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            draft = root / "chapters"
            draft.mkdir()
            for filename, heading in zip(SECTION_FILES, EXPECTED_HEADINGS, strict=True):
                (draft / filename).write_text(heading + "\n\nTest section.\n", encoding="utf-8")
            output = root / "out" / "nouveau-roman.txt"
            manifest = root / "out" / "manifest.txt"
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--draft-dir", str(draft),
                 "--output", str(output), "--manifest", str(manifest),
                 "--minimum-words", "1"],
                cwd=ROOT, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(output.exists())
            self.assertIn("nouveau-roman.txt", manifest.read_text(encoding="utf-8"))
            self.assertNotIn("resurrectes_version_codex.txt", manifest.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
