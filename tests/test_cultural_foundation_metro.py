import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from bs4 import BeautifulSoup
from unittest.mock import patch

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

    def test_new_shared_municipal_boards_filter_unrelated_posts(self):
        for fid, name, unrelated in (
            ("seoul:guro", "구로문화재단", "구로구청 일반임기제 채용 공고"),
            ("gyeonggi:hanam", "하남문화재단", "하남시 기간제근로자 채용 공고"),
        ):
            foundation = {"id": fid, "name": name, "aliases": [f"(재){name}"]}
            self.assertTrue(crawler.candidate_belongs_to_foundation(foundation, f"{name} 직원 채용"))
            self.assertFalse(crawler.candidate_belongs_to_foundation(foundation, unrelated))
            self.assertFalse(crawler.foundation_owned_board_host(foundation, "https://www.hanam.go.kr/www/"))

    def test_initial_rollout_uses_only_three_detail_verified_new_boards(self):
        baseline = {
            "seoul:metropolitan",
            "incheon:metropolitan", "incheon:jemulpo", "incheon:seohae",
            "incheon:yeonsu", "incheon:bupyeong", "incheon:namdong",
        }
        first_batch = {"seoul:yangcheon", "seoul:yeongdeungpo", "gyeonggi:yangpyeong"}
        configured = {x["id"] for x in self.registry["institutions"] if x.get("officialRecruitmentUrl")}
        self.assertEqual(configured, baseline | first_batch)

    def test_board_navigation_cannot_be_published_as_detail(self):
        self.assertFalse(crawler.official_position_title("채용공고"))
        self.assertFalse(crawler.looks_like_detail_url(
            "https://www.swcf.or.kr/?p=116", "https://www.swcf.or.kr/?p=116&bxPage=1"))
        self.assertFalse(crawler.looks_like_detail_url(
            "https://www.ydpcf.or.kr/board.do?bid=3&p=1", "https://www.ydpcf.or.kr/board.do?bid=3"))
        self.assertTrue(crawler.looks_like_detail_url(
            "https://ypcf.or.kr/recruit", "https://ypcf.or.kr/recruit/?bmode=view&idx=174131299"))

    def test_access_page_js_shell_and_js_detail_are_unhealthy(self):
        foundation = {"id": "gyeonggi:yangpyeong", "name": "양평문화재단", "homepage": "https://ypcf.or.kr/"}
        examples = (
            "<html><body>양평문화재단 WELLCONN 접근 대기</body></html>",
            "<html ng-app='recruit'><body>양평문화재단 채용 {{item.title}}</body></html>",
            "<html><body>양평문화재단 채용 <a href='javascript:reg_view(25)'>직원 채용 공고</a></body></html>",
            "<html><body>양평문화재단 채용</body></html>",
        )
        for html in examples:
            response = SimpleNamespace(url="https://ypcf.or.kr/recruit", text=html, content=html.encode())
            with self.subTest(html=html), self.assertRaises(RuntimeError):
                crawler.verify_board_surface(BeautifulSoup(html, "html.parser"), foundation, response, {})
        self.assertTrue(crawler.foundation_owned_board_host(foundation, "https://ypcf.or.kr/recruit"))

    def test_https_redirect_to_http_fails(self):
        response = SimpleNamespace(url="http://ypcf.or.kr/recruit", encoding="utf-8", raise_for_status=lambda: None)
        session = SimpleNamespace(get=lambda *args, **kwargs: response)
        with self.assertRaisesRegex(RuntimeError, "downgraded"):
            crawler.resilient_request(session, "https://ypcf.or.kr/recruit")

    def test_secondary_sfac_board_requires_explicit_empty_text(self):
        response = SimpleNamespace(url="https://sfac.careerlink.kr/", status_code=200,
                                   text="<html><body>서울문화재단 채용</body></html>")
        with patch.object(crawler, "resilient_request", return_value=response):
            with self.assertRaisesRegex(RuntimeError, "lacks an explicit empty state"):
                crawler.sfac_careerlink_probe(None)

    def test_position_scope_includes_jobs_and_teaching_people(self):
        included = [
            "2026년 제7회 직원 채용 공고",
            "문화예술 교육 강사 모집 공고",
            "기간제근로자 채용 공고",
            "대표이사 공개모집 공고",
            "구립합창단 단원 추가모집 공고",
        ]
        for title in included:
            self.assertTrue(crawler.official_position_title(title), title)

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
