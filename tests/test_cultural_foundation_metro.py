import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, "scripts")
import crawl_official_foundation_jobs_v2 as crawler


class CulturalFoundationMetroTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads(Path("cultural_foundation_registry.json").read_text(encoding="utf-8"))

    def test_registry_is_55_across_three_regions(self):
        rows = [x for x in self.registry["institutions"] if x.get("enabled") is not False]
        self.assertEqual(len(rows), 55)
        by_region = {}
        for row in rows:
            by_region[row["region"]] = by_region.get(row["region"], 0) + 1
        self.assertEqual(by_region, {"서울": 24, "경기": 25, "인천": 6})

    def test_incheon_current_six_foundations_are_registered(self):
        rows = {x["id"]: x for x in self.registry["institutions"] if x.get("region") == "인천"}
        self.assertEqual(
            set(rows),
            {
                "incheon:metropolitan",
                "incheon:jemulpo",
                "incheon:seohae",
                "incheon:yeonsu",
                "incheon:bupyeong",
                "incheon:namdong",
            },
        )
        self.assertEqual(rows["incheon:jemulpo"]["name"], "제물포문화재단")
        self.assertIn("인천중구문화재단", rows["incheon:jemulpo"]["aliases"])
        self.assertEqual(rows["incheon:seohae"]["name"], "인천서해구문화재단")
        self.assertIn("인천서구문화재단", rows["incheon:seohae"]["aliases"])
        self.assertTrue(all(x.get("officialRecruitmentUrl") for x in rows.values()))
        self.assertIn("namdong.go.kr", rows["incheon:namdong"]["officialRecruitmentUrl"])
        self.assertIn("namdongcf.or.kr", rows["incheon:namdong"]["canonicalRecruitmentUrl"])

    def test_namdong_shared_official_board_filters_other_agencies(self):
        foundation = {
            "id": "incheon:namdong",
            "name": "남동문화재단",
            "aliases": ["(재)남동문화재단", "재단법인 남동문화재단"],
        }
        self.assertTrue(crawler.candidate_belongs_to_foundation(foundation, "(재)남동문화재단 2026년 기간제근로자 채용 공고"))
        self.assertFalse(crawler.candidate_belongs_to_foundation(foundation, "서울특별시 송파구 시간선택임기제공무원 채용공고"))

    def test_position_scope_includes_jobs_and_teaching_people(self):
        included = [
            "2026년 제7회 직원 채용 공고",
            "문화예술 교육 강사 모집 공고",
            "기간제근로자 채용 공고",
            "대표이사 공개모집 공고",
            "구립합창단 단원 추가모집 공고",
            "성북문화재단 성북구립미술관 아르바이트(운영보조) 모집 공고",
        ]
        for title in included:
            self.assertTrue(crawler.official_position_title(title), title)

    def test_seongbuk_official_board_uses_compatible_cache_header(self):
        row = next(x for x in self.registry["institutions"] if x["id"] == "seoul:seongbuk")
        self.assertIn("sbculture.or.kr/culture/bbs/BMSR00034/list.do", row["officialRecruitmentUrl"])
        response = Mock(status_code=200, encoding="utf-8")
        response.raise_for_status.return_value = None
        session = Mock()
        session.get.return_value = response
        crawler.resilient_request(session, row["officialRecruitmentUrl"])
        self.assertEqual(session.get.call_args.kwargs["headers"]["Cache-Control"], "no-cache")
        crawler.resilient_request(session, "https://www.jcf.or.kr/main/inform/job.jsp")
        self.assertEqual(session.get.call_args.kwargs["headers"]["Cache-Control"], "no-cache, no-store, max-age=0")

    def test_position_scope_excludes_program_participants_and_results(self):
        excluded = [
            "문화예술교육 참여자 모집",
            "생활문화 동아리 모집 공고",
            "하반기 정기대관 모집 공고",
            "문화예술활동 지원사업 공모",
            "기간제근로자 채용 면접시험 합격자 결정 공고",
            "제안서 평가위원 후보자 모집 공고",
        ]
        for title in excluded:
            self.assertFalse(crawler.official_position_title(title), title)

    def test_nsart_stale_list_rows_are_not_fetched_as_current(self):
        today = crawler.base.date(2026, 9, 26)
        self.assertFalse(
            crawler.base.nsart_candidate_in_window(
                {"registered": crawler.base.date(2026, 5, 1)},
                today,
            )
        )
        self.assertTrue(
            crawler.base.nsart_candidate_in_window(
                {"registered": crawler.base.date(2026, 9, 7)},
                today,
            )
        )
        self.assertTrue(crawler.base.nsart_candidate_in_window({"registered": None}, today))

    def test_native_detail_identity_prefers_query_id(self):
        self.assertEqual(
            crawler.detail_identity("https://www.jcf.or.kr/main/bbs/bbsMsgDetail.do?bcd=recruit&msg_seq=118"),
            "msg_seq:118",
        )
        self.assertEqual(
            crawler.detail_identity("https://www.bpcf.or.kr/bpcf/bbs/BMSR00001/view.do?boardId=13000&menuNo=200059"),
            "boardId:13000",
        )


if __name__ == "__main__":
    unittest.main()
