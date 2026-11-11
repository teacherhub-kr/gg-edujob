"""Behavioral smoke checks for blocked-official private publication decisions."""
import unittest
from scripts.production_supervisor import private_action_for_official_block


class BlockedOfficialSimulationTests(unittest.TestCase):
    def test_official_blocked_uses_private_dispatch(self):
        for blocked in ("skip-fast-circuit-open", "skip-fast-backoff"):
            self.assertEqual(
                private_action_for_official_block(
                    blocked, lambda: ("private-lessoninfo", "overdue")
                )[0],
                "private-lessoninfo",
            )

    def test_official_or_unified_runnable_never_preempted(self):
        for action in ("fast", "recovery", "unified", "skip-active-run"):
            self.assertEqual(
                private_action_for_official_block(
                    action, lambda: ("private-lessoninfo", "overdue")
                ),
                (None, None),
            )

    def test_private_backoff_not_dispatched(self):
        self.assertEqual(
            private_action_for_official_block(
                "skip-fast-circuit-open",
                lambda: ("skip-private-backoff", "cooldown"),
            ),
            (None, "cooldown"),
        )


if __name__ == "__main__":
    unittest.main()
