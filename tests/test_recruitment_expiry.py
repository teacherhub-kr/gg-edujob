"""Expiry rules for official, private and foundation job projections."""
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_unified_search as base


class RecruitmentExpiryTests(unittest.TestCase):
    def test_ordinary_day_only_deadline_is_valid_through_closing_date(self):
        current = datetime(2026, 11, 25, 17, 1, tzinfo=base.KST)
        self.assertFalse(base.deadline_expired("2026-11-25", now=current))
        self.assertTrue(base.deadline_expired("2026-11-24", now=current))
        self.assertFalse(base.deadline_expired("2026-11-26", now=current))

    def test_explicit_clock_uses_korean_time_and_expires_at_cutoff(self):
        before = datetime(2026, 11, 25, 16, 59, tzinfo=base.KST)
        after = datetime(2026, 11, 25, 17, 1, tzinfo=base.KST)
        for ending in ("2026-11-25 17:00", "2026-11-25T17:00:00", "2026.11.25 17:00"):
            with self.subTest(ending=ending):
                self.assertFalse(base.deadline_expired(ending, now=before))
                self.assertTrue(base.deadline_expired(ending, now=after))

    def test_missing_deadline_is_not_arbitrarily_considered_expired(self):
        current = datetime(2026, 11, 25, 17, 1, tzinfo=base.KST)
        self.assertFalse(base.deadline_expired("", now=current))
        self.assertFalse(base.deadline_expired(None, now=current))

    def test_closed_known_deadline_removed_from_official_and_private(self):
        yesterday = (base.TODAY - timedelta(days=1)).isoformat()
        official = {"title": "교사 채용 공고", "registered": yesterday, "applyEnd": yesterday}
        private = {**official, "province": "서울"}
        self.assertFalse(base.official_current(official, set()))
        self.assertFalse(base.private_current(private))

    def test_known_future_deadline_preserves_current_post(self):
        tomorrow = (base.TODAY + timedelta(days=1)).isoformat()
        row = {"title": "기간제교사 채용 공고", "registered": base.TODAY.isoformat(),
               "applyEnd": tomorrow, "province": "경기"}
        self.assertTrue(base.official_current(row, set()))
        self.assertTrue(base.private_current(row))


if __name__ == "__main__":
    unittest.main()
