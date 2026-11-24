#!/usr/bin/env python3
"""Guard event-driven supervisor wakeups against PR/branch loops and cron drift."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/production-operations-watchdog.yml"


class SupervisorCompletionWakeupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = WORKFLOW.read_text(encoding="utf-8")

    def test_only_existing_production_workflows_wake_supervisor(self):
        block = self.source.split("  workflow_run:", 1)[1].split("  pull_request:", 1)[0]
        self.assertIn("types: [completed]", block)
        names = re.findall(r"^\s+- '([^']+)'$", block, re.MULTILINE)
        self.assertEqual(names, [
            "Verified Seoul-Gyeonggi official refresh (Incheon isolated)",
            "Unified recruitment search",
            "Independent guarded private recruitment scheduler",
        ])
        self.assertNotIn("Production operations watchdog", block)

    def test_pr_runs_contract_only_and_cannot_dispatch(self):
        self.assertIn("contract:\n    if: github.event_name == 'pull_request'", self.source)
        self.assertIn("python -m unittest tests.test_supervisor_completion_wakeup", self.source)
        gate = self.source.split("  watchdog:\n", 1)[1].split("    runs-on:", 1)[0]
        self.assertIn("github.event_name == 'workflow_run'", gate)
        self.assertIn("github.event.workflow_run.head_branch == 'main'", gate)
        self.assertIn("github.event.workflow_run.event == 'workflow_dispatch'", gate)
        self.assertIn("github.event.workflow_run.event == 'schedule'", gate)
        self.assertNotIn("github.event_name == 'pull_request' ||", gate)

    def test_existing_four_quarter_hour_schedules_still_present(self):
        for cron in ("8 * * * *", "23 * * * *", "38 * * * *", "53 * * * *"):
            self.assertIn(f"- cron: '{cron}'", self.source)
        self.assertIn("group: production-operations-watchdog", self.source)
        self.assertIn("cancel-in-progress: false", self.source)

    def test_existing_action_guard_and_unique_dispatch_recheck_unchanged(self):
        self.assertIn("python scripts/private_refresh_policy.py", self.source)
        self.assertIn("python scripts/seoul_gyeonggi_watchdog.py", self.source)
        self.assertIn("Production workflow already active; no duplicate dispatch", self.source)
        self.assertIn("select(.event == \\"workflow_dispatch\\"", self.source)


if __name__ == "__main__":
    unittest.main()
