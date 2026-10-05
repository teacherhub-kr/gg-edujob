import copy
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from scripts import production_supervisor as supervisor
from scripts.private_refresh_policy import (
    CLEANEYE_KEY,
    CLEANEYE_REPORT,
    CLEANEYE_WORKFLOW,
    FOUNDATION_REPORT,
    LESSONINFO_LINK_KEY,
    LESSONINFO_LINK_REPORT,
    LESSONINFO_LINK_WORKFLOW,
    LESSONINFO_SOURCE_REPORT,
    PRIVATE_REFRESH_TARGET_HOURS,
    apply_private_refresh_policy,
    register_lessoninfo_link_verification,
)


class PrivateRefreshPolicyTests(unittest.TestCase):
    def test_private_sources_refresh_before_previous_freshness_budget(self):
        original_private = copy.deepcopy(supervisor.PRIVATE_REFRESH_TARGETS)
        original_targets = copy.deepcopy(supervisor.TARGETS)
        original_events = copy.deepcopy(supervisor.PRODUCTION_EVENTS)
        original_backoff = copy.deepcopy(supervisor.CIRCUIT_BACKOFF_HOURS)
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
                    original_private[key]["maxAgeHours"],
                )
                self.assertLess(refresh_hours, original_private[key]["maxAgeHours"])

            cleaneye = supervisor.PRIVATE_REFRESH_TARGETS[CLEANEYE_KEY]
            self.assertEqual(cleaneye["workflow"], CLEANEYE_WORKFLOW)
            self.assertEqual(cleaneye["report"], CLEANEYE_REPORT)
            self.assertEqual(cleaneye["maxAgeHours"], 4)
            self.assertEqual(cleaneye["hardFreshnessBudgetHours"], 6)
            self.assertEqual(supervisor.TARGETS[CLEANEYE_KEY], CLEANEYE_WORKFLOW)
            self.assertEqual(
                supervisor.PRODUCTION_EVENTS[CLEANEYE_WORKFLOW], {"workflow_dispatch"}
            )
            self.assertEqual(
                supervisor.PRIVATE_REFRESH_TARGETS["private-foundation"]["report"],
                FOUNDATION_REPORT,
            )
        finally:
            supervisor.PRIVATE_REFRESH_TARGETS.clear()
            supervisor.PRIVATE_REFRESH_TARGETS.update(original_private)
            supervisor.TARGETS.clear()
            supervisor.TARGETS.update(original_targets)
            supervisor.PRODUCTION_EVENTS.clear()
            supervisor.PRODUCTION_EVENTS.update(original_events)
            supervisor.CIRCUIT_BACKOFF_HOURS.clear()
            supervisor.CIRCUIT_BACKOFF_HOURS.update(original_backoff)

    def test_official_refresh_policy_is_unchanged(self):
        self.assertEqual(supervisor.FAST_REFRESH_AFTER, timedelta(hours=3, minutes=15))
        self.assertEqual(supervisor.P0_STALE_AFTER, timedelta(hours=6))

    def test_watchdog_uses_policy_wrapper_as_single_dispatcher(self):
        text = Path(".github/workflows/fast-refresh-watchdog.yml").read_text(encoding="utf-8")
        self.assertIn("python scripts/private_refresh_policy.py", text)
        self.assertNotIn("python scripts/production_supervisor.py \\", text)
        self.assertIn(
            "private-lessoninfo-links) workflow='lessoninfo-culture-cold-verify.yml'",
            text,
        )
        self.assertIn(
            "private-cleaneye) workflow='update-cleaneye-jobs.yml'",
            text,
        )
        self.assertEqual(text.count("schedule:"), 1)

    def test_cleaneye_writer_is_dispatch_only(self):
        text = Path(".github/workflows/update-cleaneye-jobs.yml").read_text(encoding="utf-8")
        trigger = text.split("permissions:", 1)[0]
        self.assertIn("workflow_dispatch:", trigger)
        self.assertNotIn("schedule:", trigger)
        self.assertNotIn("workflow_run:", trigger)
        self.assertIn("crawl_cleaneye_foundation_jobs.py", text)
        self.assertIn("missingAfterCount", text)

    def test_lessoninfo_source_advance_prioritizes_cold_link_verification(self):
        original_private = copy.deepcopy(supervisor.PRIVATE_REFRESH_TARGETS)
        original_targets = copy.deepcopy(supervisor.TARGETS)
        original_events = copy.deepcopy(supervisor.PRODUCTION_EVENTS)
        original_backoff = copy.deepcopy(supervisor.CIRCUIT_BACKOFF_HOURS)
        source_at = datetime.fromisoformat("2026-10-05T12:00:00+09:00")
        link_at = datetime.fromisoformat("2026-10-05T08:00:00+09:00")

        def commit_time(path):
            if path == LESSONINFO_SOURCE_REPORT:
                return source_at
            if path == LESSONINFO_LINK_REPORT:
                return link_at
            return None

        try:
            with patch.object(supervisor, "git_commit_time", side_effect=commit_time):
                register_lessoninfo_link_verification()
            spec = supervisor.PRIVATE_REFRESH_TARGETS[LESSONINFO_LINK_KEY]
            self.assertEqual(spec["workflow"], LESSONINFO_LINK_WORKFLOW)
            self.assertEqual(spec["maxAgeHours"], 1)
            self.assertTrue(spec["dependencyNewer"])
            self.assertEqual(supervisor.TARGETS[LESSONINFO_LINK_KEY], LESSONINFO_LINK_WORKFLOW)
            self.assertEqual(
                supervisor.PRODUCTION_EVENTS[LESSONINFO_LINK_WORKFLOW],
                {"workflow_dispatch"},
            )
        finally:
            supervisor.PRIVATE_REFRESH_TARGETS.clear()
            supervisor.PRIVATE_REFRESH_TARGETS.update(original_private)
            supervisor.TARGETS.clear()
            supervisor.TARGETS.update(original_targets)
            supervisor.PRODUCTION_EVENTS.clear()
            supervisor.PRODUCTION_EVENTS.update(original_events)
            supervisor.CIRCUIT_BACKOFF_HOURS.clear()
            supervisor.CIRCUIT_BACKOFF_HOURS.update(original_backoff)

    def test_lessoninfo_cold_verifier_remains_dispatch_only_and_fail_closed(self):
        cold = Path(".github/workflows/lessoninfo-culture-cold-verify.yml").read_text(encoding="utf-8")
        trigger = cold.split("permissions:", 1)[0]
        self.assertIn("workflow_dispatch:", trigger)
        self.assertNotIn("workflow_run:", trigger)
        self.assertNotIn("schedule:", trigger)
        self.assertIn("unverified culture rows expose URLs", cold)
        self.assertIn("cold-browser-artmore-id-title-match", cold)


if __name__ == "__main__":
    unittest.main()
