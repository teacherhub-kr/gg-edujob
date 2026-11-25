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


    def test_terminal_status_in_title_overrides_future_or_unknown_end_date(self):
        end = (base.TODAY + timedelta(days=35)).isoformat()
        positive = (
            "[푸른솔유치원] 2026 방과후 인력 채용 (2차)(접수마감)",
            "유치원 음악강사 채용 [구인완료]",
            "마감 2026학년도 초등학교 강사 모집 재공고(채용마감)",
            "시간제 자원봉사자 모집 공고(2차)-접수 마감",
            "음악강사 (구인완료 )",
        )
        for title in positive:
            with self.subTest(title=title):
                self.assertTrue(base.explicitly_closed_title(title))
                row = {"title": title, "registered": base.TODAY.isoformat(),
                       "applyEnd": end, "province": "경기"}
                self.assertFalse(base.official_current(row, set()))
                self.assertFalse(base.private_current(row))

    def test_deadline_explanation_and_future_announcement_are_not_closed(self):
        future = (base.TODAY + timedelta(days=30)).isoformat()
        titles = (
            "2027년 서류 접수 마감일 변경 안내",
            "원서 접수마감 시간 18시 공지",
            "기간제교사 채용 공고(2차)",
            "2027년 1월 4일 접수 마감 예정 공고",
        )
        for title in titles:
            with self.subTest(title=title):
                self.assertFalse(base.explicitly_closed_title(title))
                row = {"title": title, "registered": base.TODAY.isoformat(),
                       "applyEnd": future, "province": "경기"}
                self.assertTrue(base.official_current(row, set()))

    def test_closed_foundation_and_lessoninfo_candidates_are_not_public(self):
        from build_unified_search_multi import foundation_official_current
        from private_source_registry import lessoninfo_full_candidate_publishable
        future = (base.TODAY + timedelta(days=7)).isoformat()
        f = {
            "title": "문화재단 직원 채용 공고 (접수마감)", "province": "경기",
            "registered": base.TODAY.isoformat(), "applyEnd": future,
            "sourceRole": "primary-official", "detailLinkVerified": True,
            "transportVerified": True, "foundationRegistryId": "gyeonggi:sample",
            "sourceIdentity": "official-foundation:test:100",
            "url": "https://example.org/job/100",
        }
        self.assertFalse(foundation_official_current(f))
        self.assertFalse(lessoninfo_full_candidate_publishable({
            "title": "일일 음악강사 모집 [구인완료]", "statusGroup": "current",
            "applyEnd": future, "registered": base.TODAY.isoformat(),
        }))


if __name__ == "__main__":
    unittest.main()
