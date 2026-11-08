"""Hermetic end-to-end watchdog decision regression tests."""
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock
from scripts import production_supervisor as ps

KST = timezone(timedelta(hours=9))
NOW = datetime(2026, 11, 8, 14, 45, tzinfo=KST)
OFFICIAL = datetime(2026, 10, 12, 15, 54, tzinfo=KST)
OLD_UNIFIED = datetime(2026, 10, 12, 18, 18, tzinfo=KST)
PRIVATE = datetime(2026, 10, 15, 2, 36, tzinfo=KST)
counter = 1000

def run(minutes_ago, conclusion="failure", status="completed"):
    global counter
    counter += 1
    stamp = (NOW - timedelta(minutes=minutes_ago)).isoformat()
    return {"id": counter, "status": status,
            "conclusion": conclusion if status == "completed" else None,
            "event": "workflow_dispatch", "head_branch": "main",
            "created_at": stamp, "run_started_at": stamp, "updated_at": stamp}

FAST_CIRCUIT = [run(30), run(120), run(240)]
RECOVERY_BACKOFF = [run(60)]

class WatchdogDecisionE2ETests(unittest.TestCase):
    def decide(self, runs, *, active=(), unified_time=None, private_time=PRIVATE):
        files = {filename: key for key, filename in ps.TARGETS.items()}
        commits = {"jobs.json": OFFICIAL,
                   "unified_jobs.json": unified_time or (NOW - timedelta(minutes=5))}
        for spec in ps.PRIVATE_REFRESH_TARGETS.values():
            commits[spec["report"]] = private_time
        real_load = ps.load_json

        def load(path, default):
            if str(path) == "collector_status.json":
                return {"fast": {"state": "failure",
                        "lastSuccessAt": OFFICIAL.isoformat(),
                        "updatedAt": OFFICIAL.isoformat()}}
            if str(path) == "artmore_reconciliation_report.candidate.json":
                return {}
            return real_load(path, default)

        def gh_runs(_repo, filename):
            key = files.get(filename)
            return ps.production_runs(filename, list(runs.get(key, []))) if key else []

        with mock.patch.object(ps, "gh_runs", gh_runs), \
             mock.patch.object(ps, "gh_active_target_keys", lambda _repo: set(active)), \
             mock.patch.object(ps, "git_commit_time", lambda path: commits.get(path)), \
             mock.patch.object(ps, "git_change_count_after", lambda since, paths: 0), \
             mock.patch.object(ps, "load_json", load), \
             mock.patch.object(ps, "registry_contract_status", lambda reg, jobs: (True, {})):
            return ps.compute_state(NOW, "owner/repo")

    def test_unpublished_private_backlog_rebuilds_unified_first(self):
        state = self.decide({"fast": FAST_CIRCUIT, "recovery": RECOVERY_BACKOFF},
                            unified_time=OLD_UNIFIED)
        self.assertEqual(state["action"], "unified")
        self.assertTrue(state["p0Incident"])

    def test_fast_circuit_open_dispatches_private(self):
        state = self.decide({"fast": FAST_CIRCUIT, "recovery": RECOVERY_BACKOFF})
        self.assertTrue(state["action"].startswith("private-"), state)
        self.assertTrue(state["p0Incident"])

    def test_fast_backoff_dispatches_private(self):
        state = self.decide({"fast": [run(20)], "recovery": RECOVERY_BACKOFF})
        self.assertTrue(state["action"].startswith("private-"), state)

    def test_fast_not_preempted(self):
        self.assertEqual(self.decide({"fast": [run(130)], "recovery": RECOVERY_BACKOFF})["action"], "fast")

    def test_recovery_not_preempted(self):
        self.assertEqual(self.decide({"fast": FAST_CIRCUIT,
                                      "recovery": [run(600, "success")]})["action"], "recovery")

    def test_unified_circuit_open_no_retry_loop(self):
        state = self.decide({"fast": FAST_CIRCUIT, "recovery": RECOVERY_BACKOFF,
                             "unified": [run(30), run(90), run(150)]},
                            unified_time=OLD_UNIFIED)
        self.assertNotEqual(state["action"], "unified")
        self.assertTrue(state["p0Incident"])

    def test_active_private_not_duplicated(self):
        state = self.decide({"fast": FAST_CIRCUIT, "recovery": RECOVERY_BACKOFF,
                             "private-lessoninfo": [run(5, status="in_progress")]},
                            active=("private-lessoninfo",))
        self.assertFalse(state["action"].startswith("private-"), state)

    def test_private_circuit_open_no_retry(self):
        runs = {key: [run(30), run(60), run(90)] for key in ps.PRIVATE_REFRESH_TARGETS}
        runs.update({"fast": FAST_CIRCUIT, "recovery": RECOVERY_BACKOFF})
        state = self.decide(runs)
        self.assertFalse(state["action"].startswith("private-"), state)
        self.assertTrue(state["p0Incident"])

if __name__ == "__main__":
    unittest.main()
