"""Exercise real hardener entry points on isolated current/legacy/broken fixtures."""
import ast
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]


class HardeningTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.gettempdir()) / ("fast-hardening-" + uuid.uuid4().hex)
        self.root.mkdir(mode=0o777)
        shutil.copytree(ROOT / "scripts", self.root / "scripts")

    def tearDown(self):
        shutil.rmtree(self.root)

    def run_script(self, name, success=True):
        result = subprocess.run([sys.executable, str(self.root / "scripts" / name)],
                                cwd=self.root, capture_output=True, text=True,
                                encoding="utf-8", env={**os.environ, "PYTHONUTF8": "1"})
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result.stdout + result.stderr

    def hashes(self):
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (self.root / "scripts").glob("*.py")}

    def replace(self, name, before, after):
        path = self.root / "scripts" / name
        text = path.read_text(encoding="utf-8")
        self.assertIn(before, text)
        path.write_text(text.replace(before, after, 1), encoding="utf-8")

    def test_current_twice_unchanged(self):
        before = self.hashes()
        for _ in range(2):
            for script in ("harden_fast_pagination.py", "harden_network_retries.py"):
                self.assertIn("already hardened", self.run_script(script))
            self.assertEqual(before, self.hashes())

    def test_partial_pagination_fails_closed(self):
        self.replace("scrape_jobs.py", "fully_dated = len(page_dates) == page_candidates",
                     "fully_dated = True")
        before = self.hashes()
        self.assertIn("Partial support pagination", self.run_script("harden_fast_pagination.py", False))
        self.assertEqual(before, self.hashes())

    def test_partial_retry_fails_closed(self):
        self.replace("scrape_jobs.py", 'S.mount("http://", HTTPAdapter(max_retries=RETRY_POLICY))', "")
        before = self.hashes()
        self.assertIn("Partial or unrecognized retry", self.run_script("harden_network_retries.py", False))
        self.assertEqual(before, self.hashes())

    def test_weakened_retry_fails_closed(self):
        self.replace("scrape_jobs.py", "total=3, connect=3", "total=0, connect=3")
        self.assertIn("Partial or unrecognized retry", self.run_script("harden_network_retries.py", False))

    def test_missing_required_session_fails_closed(self):
        self.replace("scrape_jobs.py", "S = requests.Session()", "S = None")
        self.assertIn("Required collector session missing", self.run_script("harden_network_retries.py", False))

    def test_legacy_retry_installs_then_noop(self):
        path = self.root / "scripts/scrape_jobs.py"
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        nodes = [n for n in tree.body if (
            isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "RETRY_POLICY" for t in n.targets)
        ) or (isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
              and isinstance(n.value.func, ast.Attribute) and n.value.func.attr == "mount")]
        for node in reversed(nodes):
            lines = text.splitlines(keepends=True)
            text = "".join(lines[:node.lineno-1] + lines[node.end_lineno:])
        path.write_text(text, encoding="utf-8")
        self.run_script("harden_network_retries.py")
        before = self.hashes()
        self.run_script("harden_network_retries.py")
        self.assertEqual(before, self.hashes())

    def test_partial_verifier_fails_closed(self):
        self.replace("verify_jobs.py", 'session.mount("http://", adapter)', "")
        self.assertIn("Partial or unrecognized retry", self.run_script("harden_network_retries.py", False))


if __name__ == "__main__":
    unittest.main()
