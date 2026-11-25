"""Contracts for hourly guarded official scheduler while Incheon stays held."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ScheduledOfficialCollectionContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = (ROOT / ".github/workflows/seoul-gyeonggi-official.yml").read_text(encoding="utf-8")

    def test_hourly_heartbeat_preserves_bounded_collection(self):
        self.assertIn("cron: '17 * * * *'", self.workflow)
        self.assertNotIn("cron: '17 */3 * * *'", self.workflow)
        policy = (ROOT / "scripts/seoul_gyeonggi_watchdog.py").read_text(encoding="utf-8")
        self.assertIn("REGIONAL_REFRESH_AFTER = timedelta(hours=4)", policy)
        self.assertIn("scheduled_official_dispatch:", self.workflow)
        self.assertIn("if: github.event_name == 'schedule'", self.workflow)

    def test_schedule_dispatches_only_approved_workflow_after_guard(self):
        scheduled = self.workflow.split("  scheduled_official_dispatch:", 1)[1].split("  guri_official_live_proof:", 1)[0]
        self.assertIn("seoul_gyeonggi_watchdog.py", scheduled)
        self.assertIn("--selected-action fast", scheduled)
        self.assertIn("steps.official_gate.outputs.action == 'seoul-gyeonggi'", scheduled)
        self.assertIn("gh api --method POST", scheduled)
        self.assertIn("seoul-gyeonggi-official.yml/dispatches", scheduled)
        self.assertIn("Existing official writer is active; skip duplicate dispatch", scheduled)

    def test_scheduled_trigger_does_not_run_crawler_in_place(self):
        self.assertIn("group: metro-edujob-data", self.workflow)
        regional = self.workflow.split("  regional:", 1)[1]
        self.assertIn("if: github.event_name != 'schedule'", regional)
        self.assertIn("python scripts/publish_seoul_gyeonggi_snapshot.py --merge-central", regional)
        self.assertIn("python scripts/verify_gyeonggi_central_90d.py", regional)

    def test_legacy_incheon_pipeline_remains_dispatch_only(self):
        legacy = (ROOT / ".github/workflows/update-jobs.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", legacy)
        self.assertNotIn("schedule:", legacy.split("permissions:", 1)[0])


    def test_verified_publication_replays_only_explicit_independent_ui_and_ci_paths(self):
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        from publication_transaction import _allowed
        publish = self.workflow.split("      - name: Publish only independently verified regional files", 1)[1]
        publish = publish.split("      - name:", 1)[0]
        allowed = [
            line.split("'", 2)[1]
            for line in publish.splitlines()
            if "--allow-concurrent-path '" in line
        ]
        safe_independent = {
            "app.js", "app.css", "index.html",
            "tests/test_app_frontend_contract.py",
            "tests/test_closed_jobs_visibility.js",
            ".github/workflows/m0-maintenance-freeze-audit.yml",
            ".github/workflows/update-seekle-instructor-jobs.yml",
            ".github/workflows/update-boramyc-instructor-jobs.yml",
            "scripts/pr_source_live_scope.py",
            "tests/test_private_pr_live_scope.py",
        }
        self.assertTrue(safe_independent.issubset(set(allowed)))
        self.assertIn("--revalidate-command 'python scripts/revalidate_regional_publication.py'", publish)
        self.assertIn("python scripts/publication_transaction.py publish", publish)
        self.assertTrue(_allowed(safe_independent, allowed))
        for sensitive in (
            "jobs.json", "sources.json", "source_id_ledger.json",
            "scripts/build_unified_search_multi.py",
            "scripts/verify_central_pagination.py",
            "scripts/reconcile_seoul_central_ids.py",
            "scripts/publish_seoul_gyeonggi_snapshot.py",
            "seoul_gyeonggi_jobs.json",
            "seoul_gyeonggi_refresh_report.json",
            ".github/workflows/seoul-gyeonggi-official.yml",
        ):
            with self.subTest(blocked=sensitive):
                self.assertFalse(_allowed([sensitive], allowed))
                self.assertFalse(_allowed(["app.js", sensitive], allowed))


if __name__ == "__main__":
    unittest.main()
