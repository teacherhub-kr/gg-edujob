"""Contracts for independent 3-hour official collection while Incheon stays held."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ScheduledOfficialCollectionContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = (ROOT / ".github/workflows/seoul-gyeonggi-official.yml").read_text(encoding="utf-8")

    def test_three_hour_direct_schedule(self):
        self.assertIn("cron: '17 */3 * * *'", self.workflow)
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


if __name__ == "__main__":
    unittest.main()
