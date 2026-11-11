"""Isolation and fail-closed contracts for independent private schedule."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import TestCase, mock

from scripts import scheduled_private_refresh as lane

ROOT = Path(__file__).resolve().parents[1]


class PrivateSchedulerContracts(TestCase):
    def test_workflow_is_read_only_for_pr_and_staggered_for_dispatch(self):
        s = (ROOT / ".github/workflows/independent-private-scheduler.yml").read_text()
        self.assertIn("cron: '13,43 * * * *'", s)
        self.assertIn("if: github.event_name == 'pull_request'", s)
        self.assertIn("github.event_name == 'schedule'", s)
        self.assertIn("github.ref == 'refs/heads/main'", s)
        self.assertIn("cancel-in-progress: false", s)
        self.assertIn("scripts/scheduled_private_refresh.py", s)
        self.assertIn("gh api --method POST", s)
        self.assertIn("Private writer already active:", s)
        self.assertNotIn("update-jobs.yml/dispatches", s)

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
