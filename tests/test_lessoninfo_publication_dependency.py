import unittest
from datetime import datetime
from unittest.mock import patch

from scripts import production_supervisor as supervisor
from scripts.private_refresh_policy import (
    LESSONINFO_LINK_KEY,
    LESSONINFO_LINK_REPORT,
    LESSONINFO_LINK_WORKFLOW,
    LESSONINFO_SOURCE_REPORT,
    lessoninfo_link_verification_should_precede_unified,
)


class LessonInfoPublicationDependencyTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.fromisoformat("2026-10-05T17:12:28+09:00")
        self.source_at = datetime.fromisoformat("2026-10-05T16:54:26+09:00")
        self.link_at = datetime.fromisoformat("2026-10-05T14:26:35+09:00")
        self.jobs_at = datetime.fromisoformat("2026-10-05T14:26:26+09:00")
        self.unified_at = datetime.fromisoformat("2026-10-05T16:14:04+09:00")
        self.state = {
            "action": "unified",
            "privateFreshness": {
                LESSONINFO_LINK_KEY: {
                    "overdue": True,
                }
            },
            "activePrivateTargets": [],
        }

    def commit_time(self, path):
        return {
            LESSONINFO_SOURCE_REPORT: self.source_at,
            LESSONINFO_LINK_REPORT: self.link_at,
            "jobs.json": self.jobs_at,
            "unified_jobs.json": self.unified_at,
        }.get(path)

    def test_private_only_unified_waits_for_new_lessoninfo_link_proof(self):
        with (
            patch.object(supervisor, "git_commit_time", side_effect=self.commit_time),
            patch.object(supervisor, "gh_runs", return_value=[]),
            patch.object(supervisor, "circuit_blocked", return_value=(False, 0, None)),
        ):
            self.assertTrue(
                lessoninfo_link_verification_should_precede_unified(
                    self.state, self.now, "teacherhub-kr/gg-edujob"
                )
            )

    def test_newer_official_jobs_are_never_delayed_by_lessoninfo_dependency(self):
        self.jobs_at = datetime.fromisoformat("2026-10-05T17:00:00+09:00")
        with patch.object(supervisor, "git_commit_time", side_effect=self.commit_time):
            self.assertFalse(
                lessoninfo_link_verification_should_precede_unified(
                    self.state, self.now, "teacherhub-kr/gg-edujob"
                )
            )

    def test_caught_up_link_proof_does_not_intercept_unified(self):
        self.link_at = datetime.fromisoformat("2026-10-05T16:55:00+09:00")
        with patch.object(supervisor, "git_commit_time", side_effect=self.commit_time):
            self.assertFalse(
                lessoninfo_link_verification_should_precede_unified(
                    self.state, self.now, "teacherhub-kr/gg-edujob"
                )
            )

    def test_link_verifier_backoff_is_respected(self):
        with (
            patch.object(supervisor, "git_commit_time", side_effect=self.commit_time),
            patch.object(supervisor, "gh_runs", return_value=[]),
            patch.object(supervisor, "circuit_blocked", return_value=(True, 3, self.link_at)),
        ):
            self.assertFalse(
                lessoninfo_link_verification_should_precede_unified(
                    self.state, self.now, "teacherhub-kr/gg-edujob"
                )
            )

    def test_guard_targets_only_the_cold_link_writer(self):
        self.assertEqual(LESSONINFO_LINK_KEY, "private-lessoninfo-links")
        self.assertEqual(LESSONINFO_LINK_WORKFLOW, "lessoninfo-culture-cold-verify.yml")


if __name__ == "__main__":
    unittest.main()
