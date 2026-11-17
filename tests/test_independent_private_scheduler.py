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
