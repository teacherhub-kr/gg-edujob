import copy
import unittest
from datetime import timedelta
from pathlib import Path

from scripts import production_supervisor as supervisor
from scripts.private_refresh_policy import (
    PRIVATE_REFRESH_TARGET_HOURS,
    apply_private_refresh_policy,
)


class PrivateRefreshPolicyTests(unittest.TestCase):
    def test_private_sources_refresh_before_previous_freshness_budget(self):
        original = copy.deepcopy(supervisor.PRIVATE_REFRESH_TARGETS)
        try:
            apply_private_refresh_policy()
            expected = {
                "private-lessoninfo": 4,
                "private-jobteacher": 4,
                "private-artmore-candidate": 4,
                "private-gonggonggangsa": 4,
                "private-seekle": 10,
                "private-boramyc": 10,
                "private-foundation": 22,
            }
            self.assertEqual(PRIVATE_REFRESH_TARGET_HOURS, expected)
            for key, refresh_hours in expected.items():
                self.assertEqual(
                    supervisor.PRIVATE_REFRESH_TARGETS[key]["maxAgeHours"],
                    refresh_hours,
                )
                self.assertEqual(
                    supervisor.PRIVATE_REFRESH_TARGETS[key]["hardFreshnessBudgetHours"],
                    original[key]["maxAgeHours"],
                )
                self.assertLess(refresh_hours, original[key]["maxAgeHours"])
        finally:
            supervisor.PRIVATE_REFRESH_TARGETS.clear()
            supervisor.PRIVATE_REFRESH_TARGETS.update(original)

    def test_official_refresh_policy_is_unchanged(self):
        self.assertEqual(supervisor.FAST_REFRESH_AFTER, timedelta(hours=3, minutes=15))
        self.assertEqual(supervisor.P0_STALE_AFTER, timedelta(hours=6))

    def test_watchdog_uses_policy_wrapper_as_single_dispatcher(self):
        text = Path(".github/workflows/fast-refresh-watchdog.yml").read_text(encoding="utf-8")
        self.assertIn("python scripts/private_refresh_policy.py", text)
        self.assertNotIn("python scripts/production_supervisor.py \\", text)
        self.assertEqual(text.count("schedule:"), 1)

    def test_lessoninfo_success_chains_cold_link_verification(self):
        update = Path(".github/workflows/update-lessoninfo-jobs.yml").read_text(encoding="utf-8")
        cold = Path(".github/workflows/lessoninfo-culture-cold-verify.yml").read_text(encoding="utf-8")

        update_trigger = update.split("permissions:", 1)[0]
        self.assertIn("workflow_dispatch:", update_trigger)
        self.assertNotIn("workflow_run:", update_trigger)

        cold_trigger = cold.split("permissions:", 1)[0]
        self.assertIn("workflow_dispatch:", cold_trigger)
        self.assertIn("workflow_run:", cold_trigger)
        self.assertIn("Update Lessoninfo recruitment jobs", cold_trigger)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", cold)
        self.assertIn("unverified culture rows expose URLs", cold)


if __name__ == "__main__":
    unittest.main()
