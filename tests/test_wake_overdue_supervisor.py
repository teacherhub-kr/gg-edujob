"""Regression tests for bounded, fail-closed existing-watchdog wakeups."""
import unittest
from datetime import datetime, timedelta, timezone

from scripts.wake_overdue_supervisor import should_wake


NOW = datetime(2026, 11, 25, 3, 0, tzinfo=timezone.utc)


def run(minutes_ago, status="completed", event="schedule", branch="main"):
    return {
        "status": status,
        "event": event,
        "head_branch": branch,
        "created_at": (NOW - timedelta(minutes=minutes_ago)).isoformat(),
    }


class WatchdogWakeTest(unittest.TestCase):
    def check(self, runs, expected):
        actual, reason = should_wake({"workflow_runs": runs}, NOW)
        self.assertEqual(expected, actual, reason)

    def test_overdue_wakes_existing_workflow(self):
        self.check([run(180)], True)

    def test_recent_schedule_does_not_duplicate(self):
        self.check([run(80)], False)

    def test_equal_threshold_is_not_overdue(self):
        self.check([run(90)], False)

    def test_recent_manual_dispatch_counts_as_fresh(self):
        self.check([run(180), run(20, event="workflow_dispatch")], False)

    def test_queued_and_running_protect_against_duplicates(self):
        for state in ("queued", "in_progress", "waiting", "requested", "pending"):
            with self.subTest(state=state):
                self.check([run(180), run(10, status=state)], False)

    def test_missing_or_malformed_data_fails_closed(self):
        self.assertFalse(should_wake(None, NOW)[0])
        self.assertFalse(should_wake({"workflow_runs": None}, NOW)[0])
        self.check([], False)
        self.check([{"event": "schedule", "head_branch": "main", "status": "completed"}], False)

    def test_not_main_is_not_an_authorized_wake_anchor(self):
        self.check([run(180, branch="feature")], False)

    def test_future_timestamp_is_not_accepted(self):
        self.check([run(-15)], False)

    def test_mixed_run_history_uses_freshest_valid_entry(self):
        self.check([run(181), run(91), run(30)], False)


if __name__ == "__main__":
    unittest.main()
