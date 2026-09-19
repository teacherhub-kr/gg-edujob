import unittest
from datetime import datetime, timedelta, timezone

from scripts.production_supervisor import (
    KST,
    change_after_failure,
    circuit_blocked,
    consecutive_real_failures,
    detect_source_anomalies,
    unified_publication_stale,
    unified_publication_overdue,
)


def run(conclusion, hours_ago=0, status="completed"):
    now = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
    when = (now - timedelta(hours=hours_ago)).isoformat().replace("+00:00", "Z")
    return {
        "status": status,
        "conclusion": conclusion,
        "updated_at": when,
    }


class ProductionSupervisorTests(unittest.TestCase):
    def test_unified_publication_stale_when_jobs_are_newer(self):
        jobs = datetime(2026, 9, 19, 7, 28, tzinfo=KST)
        unified = datetime(2026, 9, 10, 23, 58, tzinfo=KST)
        self.assertTrue(unified_publication_stale(jobs, unified))
        self.assertTrue(unified_publication_stale(jobs, None))
        self.assertFalse(unified_publication_stale(jobs, jobs))
        self.assertFalse(unified_publication_stale(None, unified))

    def test_unified_publication_overdue_after_four_hours(self):
        jobs = datetime(2026, 9, 19, 12, 0, tzinfo=KST)
        recent = datetime(2026, 9, 19, 9, 0, tzinfo=KST)
        stale = datetime(2026, 9, 19, 7, 0, tzinfo=KST)
        self.assertFalse(unified_publication_overdue(jobs, recent))
        self.assertTrue(unified_publication_overdue(jobs, stale))
        self.assertTrue(unified_publication_overdue(jobs, None))
        self.assertFalse(unified_publication_overdue(None, stale))

    def test_cancelled_runs_do_not_count_as_failures(self):
        runs = [run("failure"), run("cancelled"), run("failure"), run("failure"), run("success")]
        count, _ = consecutive_real_failures(runs)
        self.assertEqual(count, 3)

    def test_success_resets_failure_streak(self):
        runs = [run("failure"), run("success"), run("failure"), run("failure")]
        count, _ = consecutive_real_failures(runs)
        self.assertEqual(count, 1)

    def test_fast_circuit_blocks_three_recent_real_failures(self):
        now = datetime(2026, 9, 16, 21, 0, tzinfo=KST)
        runs = [run("failure", 0), run("failure", 1), run("failure", 2), run("success", 3)]
        blocked, failures, _ = circuit_blocked("fast", runs, now)
        self.assertTrue(blocked)
        self.assertEqual(failures, 3)

    def test_code_change_allows_controlled_probe(self):
        now = datetime(2026, 9, 16, 21, 0, tzinfo=KST)
        runs = [run("failure", 0), run("failure", 1), run("failure", 2)]
        blocked, _, _ = circuit_blocked("fast", runs, now, allow_probe_after_change=True)
        self.assertFalse(blocked)

    def test_recovery_change_after_failure_allows_only_new_contract(self):
        failure_at = datetime(2026, 9, 18, 0, 59, tzinfo=KST)
        newer_contract = datetime(2026, 9, 18, 7, 42, tzinfo=KST)
        older_contract = datetime(2026, 9, 17, 23, 0, tzinfo=KST)
        self.assertTrue(change_after_failure(newer_contract, failure_at))
        self.assertFalse(change_after_failure(older_contract, failure_at))
        self.assertFalse(change_after_failure(None, failure_at))

    def test_recovery_circuit_allows_controlled_probe_after_change(self):
        now = datetime(2026, 9, 16, 21, 0, tzinfo=KST)
        runs = [run("failure", 0), run("failure", 1), run("failure", 2)]
        blocked, failures, _ = circuit_blocked(
            "recovery", runs, now, allow_probe_after_change=True
        )
        self.assertFalse(blocked)
        self.assertEqual(failures, 3)

    def test_source_drop_is_conservative(self):
        previous = {
            "sources": [
                {"name": "A", "officialIdCount": 100, "coverageComplete": True},
                {"name": "B", "officialIdCount": 4, "coverageComplete": True},
            ]
        }
        current = {
            "sources": [
                {"name": "A", "officialIdCount": 10, "coverageComplete": True, "accessErrors": 0},
                {"name": "B", "officialIdCount": 0, "coverageComplete": True, "accessErrors": 0},
            ]
        }
        anomalies = detect_source_anomalies(current, previous)
        self.assertEqual([x["source"] for x in anomalies], ["A"])

    def test_incomplete_coverage_is_always_flagged(self):
        current = {
            "sources": [
                {"name": "A", "officialIdCount": 100, "coverageComplete": False, "accessErrors": 0},
                {"name": "B", "officialIdCount": 100, "coverageComplete": True, "accessErrors": 1},
            ]
        }
        anomalies = detect_source_anomalies(current, None)
        self.assertEqual({x["source"] for x in anomalies}, {"A", "B"})


if __name__ == "__main__":
    unittest.main()
