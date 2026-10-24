"""Portable manuscript assembly with synthetic chapters only."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.assemble_manuscript import SECTION_FILES, EXPECTED_HEADINGS, discover_sections

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


    def test_short_custom_novel_can_be_discovered(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            draft = root / 'draft'
            draft.mkdir()
            for name, heading in [('prologue.txt','PROLOGUE'),('chapter_01.txt','CHAPITRE 1'),
                                  ('chapter_02.txt','CHAPITRE 2'),('epilogue.txt','ÉPILOGUE')]:
                (draft / name).write_text(heading+'\\n\\nUne scène.\\n',encoding='utf-8')
            files = discover_sections(draft)
            self.assertEqual(len(files),4)
            output = root / 'new-novel.txt'
            result = subprocess.run(
                [sys.executable,str(SCRIPT),'--discover','--draft-dir',str(draft),
                 '--output',str(output),'--manifest',str(root/'manifest.txt'),
                 '--minimum-words','1'],
                cwd=ROOT,capture_output=True,text=True,
            )
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('CHAPITRE 2',output.read_text(encoding='utf-8'))

    def test_auto_discovery_detects_missing_middle_chapter(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'chapter_01.txt').write_text('CHAPITRE 1')
            (root/'chapter_03.txt').write_text('CHAPITRE 3')
            with self.assertRaises(ValueError):
                discover_sections(root)


if __name__ == "__main__":
    unittest.main()
