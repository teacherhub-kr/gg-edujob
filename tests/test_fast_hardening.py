"""Exercise real hardener entry points on isolated current/legacy/broken fixtures."""
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from types import SimpleNamespace

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

    def support_fixture(self):
        configured, statuses, evidence = {}, {}, []
        summary = {"generatedAt": "2026-09-14 16:00:00 KST", "reconciledSources": 38,
                   "totalSources": 38, "missingAfter": 0}
        for province, label, count in (("gyeonggi", "경기", 25), ("seoul", "서울", 11)):
            offices = [{"name": f"{label}{i}교육지원청"} for i in range(count)]
            configured[province] = {"supportOffices": offices}
            statuses[province] = {"supportOffices": [dict(o, ok=True) for o in offices]}
            for o in offices:
                board = {"url": "https://example.test/" + o["name"], "pagesScanned": 2,
                         "rawRows": 1, "coverageComplete": True, "naturalEnd": True}
                evidence.append(dict(o, province=label, coverageComplete=True, reconciled=True,
                                     boards=[board["url"]], boardHealth=[board], officialIdCount=1))
        data = {"sources": statuses, "sourceReconciliation": summary,
                "jobs": [{"sourceType": "교육지원청 개별 게시판", "detailLinkResolved": True}],
                "supportLinkResolution": {"gyeonggiExact": 1, "gyeonggiTotal": 1,
                                          "seoulExact": 1, "seoulTotal": 1}}
        report = {"summary": dict(summary), "sources": evidence}
        self.write_json("sources.json", configured)
        self.write_json("jobs.json", data)
        self.write_json("source_reconciliation_report.json", report)
        return data, report

    def write_json(self, name, value):
        (self.root / name).write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def test_fast_support_summary_requires_real_all_office_evidence(self):
        self.support_fixture()
        self.run_script("verify_support_completeness.py")
        data = json.loads((self.root / "jobs.json").read_text(encoding="utf-8"))
        self.assertEqual(data["supportCompleteness"]["gyeonggiComplete"], 25)
        self.assertEqual(data["supportCompleteness"]["seoulComplete"], 11)
        self.assertTrue(all(o["coverageEvidenceSource"] == "same-candidate-38-source-reconciliation"
                            for p in data["sources"].values() for o in p["supportOffices"]))

    def test_missing_office_proof_fails_closed(self):
        _, report = self.support_fixture()
        report["sources"].pop()
        self.write_json("source_reconciliation_report.json", report)
        self.run_script("verify_support_completeness.py", False)

    def test_stale_candidate_proof_fails_closed(self):
        _, report = self.support_fixture()
        report["summary"]["generatedAt"] = "2026-09-12 16:00:00 KST"
        self.write_json("source_reconciliation_report.json", report)
        self.run_script("verify_support_completeness.py", False)

    def test_missing_termination_proof_fails_closed(self):
        _, report = self.support_fixture()
        report["sources"][0]["boardHealth"][0]["naturalEnd"] = False
        self.write_json("source_reconciliation_report.json", report)
        self.assertIn("no explicit termination proof", self.run_script("verify_support_completeness.py", False))

    def test_unresolved_link_fails_closed(self):
        data, _ = self.support_fixture()
        data["jobs"][0]["detailLinkResolved"] = False
        self.write_json("jobs.json", data)
        self.assertIn("without exact individual links", self.run_script("verify_support_completeness.py", False))

    def test_seoul_central_is_scanned_after_all_support_offices(self):
        text = (self.root / "scripts/reconcile_source_ids.py").read_text(encoding="utf-8")
        fn = next(n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef)
                  and n.name == "crawl_official_ids")
        calls = []
        def central():
            calls.append("gyeonggi-central")
            return [{"id": "gg-central"}]
        central.last_coverage = [{"coverageComplete": True}]
        def board(url, src):
            calls.append(src["name"])
            return [{"id": src["name"]}], {"url": url, "coverageComplete": True, "pagesScanned": 1}
        def seoul_central():
            calls.append("seoul-central")
            return [{"id": "se-central"}]
        source = {"central": {"name": "central", "url": "https://example.test"}}
        cov = SimpleNamespace(SOURCES={
            "gyeonggi": {"supportOffices": [{"name": "gg-office", "boardUrls": ["https://example.test/gg"]}]},
            "seoul": {"supportOffices": [{"name": "se-office", "boardUrl": "https://example.test/se"}]}},
            CACHE={}, gyeonggi_board=board, seoul_board=lambda src: board(src["boardUrl"], src))
        namespace = {"primary": SimpleNamespace(GYEONGGI=source, SEOUL=source, scrape_seoul_central=seoul_central),
                     "cov": cov, "central_recent": SimpleNamespace(scrape_gyeonggi_central_recent=central),
                     "source_status": lambda province, name, rows, **kwargs: {"province": province, "name": name},
                     "effective_gyeonggi_metas": lambda metas, rows: metas,
                     "is_recruitment_row": lambda row: True, "source_id": lambda row: row["id"]}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), "fixture", "exec"), namespace)
        sources, rows = namespace["crawl_official_ids"]()
        self.assertEqual(calls, ["gyeonggi-central", "gg-office", "se-office", "seoul-central"])
        self.assertEqual(len(rows), 4)
        self.assertEqual(sources[1]["province"], "서울")


if __name__ == "__main__":
    unittest.main()
