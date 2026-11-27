"""Isolation and fail-closed contracts for independent private schedule."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import TestCase, mock

from scripts import scheduled_private_refresh as lane

ROOT = Path(__file__).resolve().parents[1]


class PrivateSchedulerContracts(TestCase):
    def test_workflow_is_read_only_for_pr_and_staggered_for_dispatch(self):
        s = (ROOT / ".github/workflows/independent-private-scheduler.yml").read_text()
        self.assertIn("cron: '14,44 * * * *'", s)
        self.assertIn("if: github.event_name == 'pull_request'", s)
        self.assertIn("github.event_name == 'schedule'", s)
        self.assertIn("github.ref == 'refs/heads/main'", s)
        self.assertIn("cancel-in-progress: false", s)
        self.assertIn("scripts/scheduled_private_refresh.py", s)
        self.assertIn("gh api --method POST", s)
        self.assertIn("Private writer already active:", s)
        # An isolated private collector must not race any canonical writer.
        self.assertIn("Shared production writer active:", s)
        for workflow in (
            "seoul-gyeonggi-official.yml", "update-jobs.yml",
            "recover-missing-jobs.yml", "unified-search.yml"
        ):
            self.assertIn(workflow, s)
        self.assertIn('if [ "${other_active:-0}" -gt 0 ]; then', s)
        self.assertLess(s.index("for other in seoul-gyeonggi-official.yml"), s.index("gh api --method POST"))

        self.assertNotIn("update-jobs.yml/dispatches", s)

    def test_unified_success_wakes_existing_scheduler_with_two_hour_feedback_guard(self):
        s = (ROOT / ".github/workflows/unified-search.yml").read_text()
        scheduler = (ROOT / ".github/workflows/independent-private-scheduler.yml").read_text()
        self.assertIn("wake_private_backlog:", s)
        wake = s[s.index("  wake_private_backlog:"):]
        self.assertIn("needs: build", wake)
        self.assertIn("needs.build.result == 'success'", wake)
        self.assertIn("github.event_name == 'workflow_dispatch'", wake)
        self.assertIn("github.ref == 'refs/heads/main'", wake)
        self.assertIn("actions: write", wake)
        self.assertIn("contents: read", wake)
        self.assertIn("independent-private-scheduler.yml/runs?per_page=100", wake)
        self.assertIn("event=workflow_dispatch&branch=main", wake)
        self.assertIn("(now - (.created_at | fromdateiso8601)) < 7200", wake)
        self.assertIn("Private scheduler already running or queued", wake)
        self.assertIn("Follow-on private scheduler dispatched after verified Unified success", wake)
        self.assertLess(wake.index("recent="), wake.index("active="))
        self.assertLess(wake.index("active="), wake.index("gh api --method POST"))
        # Only existing M0-approved cron events may fire the private scheduler.
        self.assertIn("cron: '14,44 * * * *'", scheduler)
        on = scheduler.split("permissions:", 1)[0]
        self.assertNotIn("workflow_run:", on)

    def test_scheduled_run_drains_eligible_sources_serially_and_bounded(self):
        s = (ROOT / ".github/workflows/independent-private-scheduler.yml").read_text()
        self.assertIn("MAX_ROUNDS: '8'", s)
        self.assertIn("DRAIN_DEADLINE_SECONDS: '2700'", s)
        self.assertIn("COLLECTOR_WAIT_SECONDS: '1500'", s)
        self.assertIn("timeout-minutes: 55", s)
        loop = s[s.index('for round in $(seq 1 "$MAX_ROUNDS"); do'):]
        self.assertLess(loop.index("git fetch -q origin main"), loop.index("scheduled_private_refresh.py"))
        self.assertLess(loop.index("Shared production writer active:"), loop.index("gh api --method POST"))
        self.assertLess(loop.index("Private writer already active:"), loop.index("gh api --method POST"))
        self.assertLess(loop.index("before_id="), loop.index("gh api --method POST"))
        self.assertLess(loop.index("gh api --method POST"), loop.index('elif length > 1'))
        self.assertIn("Ambiguous or unknown collector run", loop)
        self.assertIn("stop draining to keep one private writer", loop)
        self.assertIn('skip_args+=(--skip-action "$done_action")', loop)
        self.assertIn('completed_actions+=("$ACTION")', loop)

    def test_completed_private_source_is_excluded_from_next_decision(self):
        now = datetime.now(timezone.utc)
        key = "private-jobteacher"
        spec = {key: {"workflow": "update-jobteacher-jobs.yml", "report": "jobteacher_reconciliation_report.json", "maxAgeHours": 4}}
        with mock.patch.object(lane.policy, "apply_private_refresh_policy"), \
             mock.patch.object(lane.policy, "register_lessoninfo_link_verification"), \
             mock.patch.object(lane.supervisor, "PRIVATE_REFRESH_TARGETS", spec), \
             mock.patch.object(lane.supervisor, "gh_runs", return_value=[]), \
             mock.patch.object(lane.supervisor, "gh_active_target_keys", return_value=set()), \
             mock.patch.object(lane.supervisor, "git_commit_time", return_value=now - timedelta(hours=8)), \
             mock.patch.object(lane.supervisor, "choose_private_refresh_action", return_value=(None, None)) as policy:
            lane.choose(now, "teacherhub-kr/gg-edujob", skip_actions=(key,))
            self.assertEqual(policy.call_args.kwargs["excluded_private"], frozenset({key}))

    def test_exclusion_keeps_other_overdue_source_eligible(self):
        now = datetime.now(timezone.utc)
        supervisor = lane.supervisor
        a, b = "private-lessoninfo", "private-jobteacher"
        specs = {
            a: {"workflow": "update-lessoninfo-jobs.yml", "report": "a.json", "maxAgeHours": 4},
            b: {"workflow": "update-jobteacher-jobs.yml", "report": "b.json", "maxAgeHours": 4},
        }
        with mock.patch.object(supervisor, "PRIVATE_REFRESH_TARGETS", specs), \
             mock.patch.object(supervisor, "git_commit_time", return_value=None), \
             mock.patch.object(supervisor, "circuit_blocked", return_value=(False, 0, None)), \
             mock.patch.object(supervisor, "latest_completed", return_value=None):
            action, _ = supervisor.choose_private_refresh_action(
                now=now, all_runs={a: [], b: []},
                private_refresh_times={a: now - timedelta(hours=20), b: now - timedelta(hours=8)},
                private_freshness={
                    a: {"ageHours": 20, "maxAgeHours": 4},
                    b: {"ageHours": 8, "maxAgeHours": 4},
                },
                active_private=[], excluded_private=frozenset({a}),
            )
        self.assertEqual(action, b)

    def test_collector_and_link_verifier_share_one_group(self):
        a = (ROOT / ".github/workflows/update-lessoninfo-jobs.yml").read_text()
        b = (ROOT / ".github/workflows/lessoninfo-culture-cold-verify.yml").read_text()
        self.assertIn("group: metro-edujob-lessoninfo", a)
        self.assertIn("group: metro-edujob-lessoninfo", b)

    def test_eligible_source_comes_from_original_guard(self):
        now = datetime.now(timezone.utc)
        key = "private-jobteacher"
        spec = {key: {"workflow": "update-jobteacher-jobs.yml", "report": "jobteacher_reconciliation_report.json", "maxAgeHours": 4}}
        with mock.patch.object(lane.policy, "apply_private_refresh_policy"), \
             mock.patch.object(lane.policy, "register_lessoninfo_link_verification"), \
             mock.patch.object(lane.supervisor, "PRIVATE_REFRESH_TARGETS", spec), \
             mock.patch.object(lane.supervisor, "gh_runs", return_value=[]), \
             mock.patch.object(lane.supervisor, "gh_active_target_keys", return_value=set()), \
             mock.patch.object(lane.supervisor, "git_commit_time", return_value=now - timedelta(hours=6)), \
             mock.patch.object(lane.supervisor, "choose_private_refresh_action", return_value=(key, "due")) as policy:
            action, workflow, reason = lane.choose(now, "teacherhub-kr/gg-edujob")
        self.assertEqual((action, workflow, reason), (key, "update-jobteacher-jobs.yml", "due"))
        self.assertEqual(policy.call_count, 1)
        self.assertEqual(policy.call_args.kwargs["active_private"], [])

    def test_unknown_or_backoff_decision_never_dispatches(self):
        now = datetime.now(timezone.utc)
        spec = {"private-jobteacher": {"workflow": "update-jobteacher-jobs.yml", "report": "jobteacher_reconciliation_report.json", "maxAgeHours": 4}}
        with mock.patch.object(lane.policy, "apply_private_refresh_policy"), \
             mock.patch.object(lane.policy, "register_lessoninfo_link_verification"), \
             mock.patch.object(lane.supervisor, "PRIVATE_REFRESH_TARGETS", spec), \
             mock.patch.object(lane.supervisor, "gh_runs", return_value=[]), \
             mock.patch.object(lane.supervisor, "gh_active_target_keys", return_value=set()), \
             mock.patch.object(lane.supervisor, "git_commit_time", return_value=now - timedelta(hours=8)), \
             mock.patch.object(lane.supervisor, "choose_private_refresh_action", return_value=("skip-private-backoff", "circuit")):
            action, workflow, reason = lane.choose(now, "teacherhub-kr/gg-edujob")
        self.assertIsNone(action)
        self.assertIsNone(workflow)
        self.assertEqual(reason, "circuit")

    def test_active_writer_is_passed_to_policy(self):
        now = datetime.now(timezone.utc)
        key = "private-jobteacher"
        spec = {key: {"workflow": "update-jobteacher-jobs.yml", "report": "jobteacher_reconciliation_report.json", "maxAgeHours": 4}}
        with mock.patch.object(lane.policy, "apply_private_refresh_policy"), \
             mock.patch.object(lane.policy, "register_lessoninfo_link_verification"), \
             mock.patch.object(lane.supervisor, "PRIVATE_REFRESH_TARGETS", spec), \
             mock.patch.object(lane.supervisor, "gh_runs", return_value=[]), \
             mock.patch.object(lane.supervisor, "gh_active_target_keys", return_value={key}), \
             mock.patch.object(lane.supervisor, "git_commit_time", return_value=now - timedelta(hours=8)), \
             mock.patch.object(lane.supervisor, "choose_private_refresh_action", return_value=("skip-private-active", "writer active")) as policy:
            action, workflow, reason = lane.choose(now, "teacherhub-kr/gg-edujob")
        self.assertEqual(policy.call_args.kwargs["active_private"], [key])
        self.assertEqual((action, workflow, reason), (None, None, "writer active"))


class PrivateStarvationContracts(TestCase):
    """A repeatedly failing source must not starve independently healthy sources."""

    @staticmethod
    def failed(at, n):
        return [
            {
                "status": "completed",
                "conclusion": "failure",
                "event": "workflow_dispatch",
                "head_branch": "main",
                "run_started_at": (at - timedelta(minutes=i)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "updated_at": (at - timedelta(minutes=i)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "id": 1000 - i,
            }
            for i in range(n)
        ]

    def choose(self, now, specs, last_refresh, runs):
        supervisor = lane.supervisor
        with mock.patch.object(supervisor, "PRIVATE_REFRESH_TARGETS", specs), \
             mock.patch.object(supervisor, "git_commit_time", return_value=None):
            return supervisor.choose_private_refresh_action(
                now=now,
                all_runs=runs,
                private_refresh_times=last_refresh,
                private_freshness={
                    k: {
                        "ageHours": round((now - last_refresh[k]).total_seconds() / 3600, 2),
                        "maxAgeHours": spec["maxAgeHours"],
                    }
                    for k, spec in specs.items()
                },
                active_private=[],
            )

    def test_healthy_overdue_source_precedes_staler_failed_source(self):
        now = datetime(2026, 11, 18, 0, 0, tzinfo=timezone.utc)
        failing, healthy = "private-cleaneye", "private-lessoninfo"
        specs = {
            failing: {"workflow": "update-cleaneye-jobs.yml", "report": "a.json", "maxAgeHours": 4},
            healthy: {"workflow": "update-lessoninfo-jobs.yml", "report": "b.json", "maxAgeHours": 4},
        }
        runs = {failing: self.failed(now - timedelta(hours=9), 1), healthy: []}
        last = {failing: now - timedelta(days=36), healthy: now - timedelta(days=3)}
        self.assertEqual(self.choose(now, specs, last, runs)[0], healthy)

    def test_failing_source_can_be_probed_if_only_due_source(self):
        now = datetime(2026, 11, 18, 0, 0, tzinfo=timezone.utc)
        failing = "private-cleaneye"
        specs = {
            failing: {"workflow": "update-cleaneye-jobs.yml", "report": "a.json", "maxAgeHours": 4},
        }
        runs = {failing: self.failed(now - timedelta(hours=9), 1)}
        last = {failing: now - timedelta(days=36)}
        self.assertEqual(self.choose(now, specs, last, runs)[0], failing)

    def test_persistent_failures_backoff_exponentially_up_to_48_hours(self):
        s = lane.supervisor
        self.assertEqual(
            [s.private_failure_backoff_hours(n) for n in (0, 1, 2, 3, 4, 5, 9)],
            [0, 0, 6, 12, 24, 48, 48],
        )
        now = datetime(2026, 11, 18, 0, 0, tzinfo=timezone.utc)
        failing = "private-seekle"
        specs = {
            failing: {"workflow": "update-seekle-instructor-jobs.yml", "report": "x", "maxAgeHours": 10},
        }
        runs = {failing: self.failed(now - timedelta(hours=20), 6)}
        action, reason = self.choose(now, specs, {failing: now - timedelta(days=36)}, runs)
        self.assertEqual(action, "skip-private-backoff")
        self.assertIn(failing, reason)

    def test_unaffected_private_circuit_still_applies(self):
        now = datetime(2026, 11, 18, 0, 0, tzinfo=timezone.utc)
        failing = "private-boramyc"
        specs = {
            failing: {"workflow": "update-boramyc-instructor-jobs.yml", "report": "x", "maxAgeHours": 10},
        }
        runs = {failing: self.failed(now - timedelta(minutes=30), 3)}
        action, reason = self.choose(now, specs, {failing: now - timedelta(days=36)}, runs)
        self.assertEqual(action, "skip-private-backoff")
        self.assertIn("circuit", reason)
