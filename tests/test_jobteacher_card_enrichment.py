from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_unified_search_multi as multi


def sample_job(**overrides):
    row = {
        "sourceIdentity": "jobteacher:691652",
        "sourceId": "691652",
        "source": "잡티처",
        "sourceType": "민간 구인",
        "sourceSurface": "academy-recruitment",
        "sourceSurfaceLabel": "잡티처",
        "province": "경기",
        "provinces": ["경기"],
        "regions": ["경기 수원시"],
        "location": "경기 수원시",
        "title": "오쌤과학전문학원",
        "registered": "2026-10-09",
        "url": "https://www.jobteacher.kr/employ/detail/691652",
        "rawRowText": "오쌤과학전문학원 경기 수원시 10월 화학+생명 선생님 1명 급구/ 12월 물리+화학 선생님,중등과학~통합과학(인원 확장) 2명구인 고등부 스크랩 새창보기 과학계열 채용시까지 Today",
    }
    row.update(overrides)
    return row


class JobTeacherCardEnrichmentTests(unittest.TestCase):
    def test_extract_recruitment_copy_target_and_subjects(self):
        fields = multi.jobteacher_card_fields(sample_job())
        self.assertEqual(fields["school"], "오쌤과학전문학원")
        self.assertTrue(fields["title"].startswith("10월 화학+생명 선생님"))
        self.assertNotIn("고등부", fields["title"])
        self.assertEqual(fields["target"], "고등부")
        self.assertTrue({"물리", "화학", "생명과학", "통합과학", "과학"}.issubset(set(fields["subjects"])))

    def test_projection_keeps_academy_as_school_and_recruitment_as_title(self):
        projected = multi.project_private_generic(sample_job(), "잡티처")
        self.assertEqual(projected["school"], "오쌤과학전문학원")
        self.assertTrue(projected["title"].startswith("10월 화학+생명 선생님"))
        self.assertTrue(projected["subject"].startswith("고등부 ·"))
        self.assertIn("화학", projected["subject"])
        self.assertIn("학원강사", projected["categories"])
        self.assertIn("오쌤과학전문학원", projected["searchText"])
        self.assertIn("통합과학", projected["searchText"])

    def test_location_prefix_is_removed_without_dropping_recruitment_text(self):
        job = sample_job(
            title="(주)아이포트폴리오",
            province="서울",
            provinces=["서울", "경기"],
            regions=["서울 강서구 경기 고양시"],
            location="서울 강서구 경기 고양시",
            rawRowText="(주)아이포트폴리오 서울 강서구 경기 고양시 [리딩앤아카데미] 직영센터 영어 선생님 유/초등부 스크랩 새창보기 영어 채용시까지 10.08",
        )
        fields = multi.jobteacher_card_fields(job)
        self.assertEqual(fields["school"], "(주)아이포트폴리오")
        self.assertTrue(fields["title"].startswith("[리딩앤아카데미] 직영센터 영어 선생님"))
        self.assertEqual(fields["target"], "유/초등부")
        self.assertIn("영어", fields["subjects"])

    def test_subject_column_after_scrap_marker_is_used_for_first_screen_tags(self):
        job = sample_job(
            sourceIdentity="jobteacher:691537",
            sourceId="691537",
            title="어셔어학원",
            province="서울",
            provinces=["서울"],
            regions=["서울 서초구"],
            location="서울 서초구",
            rawRowText="어셔어학원 서울 서초구 어셔어학원 TA(조교)선생님 구인 기타 스크랩 새창보기 토익/토플/텝스 채용시까지 10.07",
        )
        fields = multi.jobteacher_card_fields(job)
        self.assertIn("TA(조교)선생님 구인", fields["title"])
        self.assertTrue({"토익", "토플", "텝스"}.issubset(set(fields["subjects"])))
        projected = multi.project_private_generic(job, "잡티처")
        self.assertIn("토익", projected["subject"])
        self.assertIn("토플", projected["searchText"])
        self.assertIn("텝스", projected["searchText"])


if __name__ == "__main__":
    unittest.main()
