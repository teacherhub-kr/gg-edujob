"""Synthetic regressions for official foundation deadline parsing (issue #393)."""
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import crawl_official_foundation_jobs as crawler


class OfficialFoundationDeadlineTest(unittest.TestCase):
    def setUp(self):
        today = datetime.now(crawler.KST).date()
        self.start = today + timedelta(days=1)
        self.end = today + timedelta(days=5)
        self.announcement_end = today + timedelta(days=25)

    @staticmethod
    def dotted(day):
        return day.strftime("%Y.%m.%d")

    def extract(self, notice):
        return crawler.extract_apply_end(notice, self.start)

    def test_announcement_period_cannot_override_application_period(self):
        text = (f"공고기간 {self.dotted(self.start)} ~ {self.dotted(self.announcement_end)} "
                f"접수기간 {self.dotted(self.start)} ~ {self.dotted(self.end)} "
                f"합격자 발표 {self.dotted(self.announcement_end)}")
        self.assertEqual(self.extract(text), self.end)

    def test_announcement_period_only_is_unverified(self):
        self.assertIsNone(self.extract(
            f"공고기간 {self.dotted(self.start)} ~ {self.dotted(self.announcement_end)}"))

    def test_application_period_ignores_interview_dates(self):
        self.assertEqual(
            self.extract(f"원서접수 {self.dotted(self.start)} ~ {self.dotted(self.end)} "
                         f"면접일자 {self.dotted(self.announcement_end)}"), self.end)

    def test_partial_year_korean_application_dates(self):
        text = (f"원서접수 {self.start.year}년 {self.start.month}월 {self.start.day}일 "
                f"~ {self.end.month}월 {self.end.day}일")
        self.assertEqual(self.extract(text), self.end)

    def test_explicit_application_cutoff(self):
        self.assertEqual(self.extract(f"접수마감 {self.dotted(self.end)} 17:00"), self.end)

    def test_explicit_application_dates_beat_recruitment_period(self):
        text = (f"모집기간 {self.dotted(self.start)} ~ {self.dotted(self.announcement_end)} "
                f"접수기간 {self.dotted(self.start)} - {self.dotted(self.end)}")
        self.assertEqual(self.extract(text), self.end)

    def test_unrelated_event_dates_are_unverified(self):
        self.assertIsNone(self.extract(
            f"서류전형 {self.dotted(self.start)} 면접일자 {self.dotted(self.end)} "
            f"합격자 발표 {self.dotted(self.announcement_end)}"))


if __name__ == "__main__":
    unittest.main()
