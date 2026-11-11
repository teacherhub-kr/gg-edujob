import json
import sys
import unittest
from pathlib import Path
from bs4 import BeautifulSoup
from unittest.mock import patch

sys.path.insert(0, "scripts")
import crawl_official_foundation_jobs_v2 as crawler
import reconcile_cultural_foundation_coverage as reconcile
import build_unified_search_multi as unified


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
        self.assertEqual(
            rows["incheon:seohae"]["officialRecruitmentUrl"],
            "https://www.seohae.go.kr/open_content/main/bbs/bbsMsgList.do?bcd=job&pgno=1",
        )
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

    def test_seohae_shared_board_excludes_other_employers_even_with_branded_context(self):
        foundation = {
            "id": "incheon:seohae",
            "name": "인천서해구문화재단",
            "aliases": ["인천서구문화재단"],
        }
        other_titles = [
            "방사선실 기간제근로자 채용 공고",
            "인천광역시 서해구 지방시간선택제임기제 마급 공무원 채용시험 시행계획 재공고(배수펌프장 관리원)",
            "인천광역시 서해구 개방형직위(보건소장) 채용시험 모집 공고",
        ]
        for title in other_titles:
            self.assertFalse(crawler.candidate_belongs_to_foundation(foundation, title))
            self.assertFalse(reconcile.municipal_official_post_belongs_to_foundation({"title": title}, foundation))
        for title in ("인천서해구문화재단 직원 채용 공고", "(재)인천서구문화재단 기간제근로자 모집"):
            self.assertTrue(crawler.candidate_belongs_to_foundation(foundation, title))
            self.assertTrue(reconcile.municipal_official_post_belongs_to_foundation({"title": title}, foundation))

        board_url = "https://www.seohae.go.kr/open_content/main/bbs/bbsMsgList.do?bcd=job"
        class Response:
            url = board_url
            text = ('<div>인천서해구문화재단 공식 채용 안내'
                    '<a href="/open_content/main/bbs/bbsMsgDetail.do?msg_seq=5076&bcd=job">'
                    '방사선실 기간제근로자 채용 공고</a></div>')
        with patch.object(crawler, "resilient_request", return_value=Response()):
            _, _, candidates, _ = crawler.list_detail_candidates(None, foundation, board_url)
        self.assertEqual(candidates, {}, "surrounding foundation branding cannot make a hospital job a foundation post")

    def test_seohae_shared_board_allows_verified_current_zero_without_hiding_parser_miss(self):
        foundation = {
            "id": "incheon:seohae",
            "name": "인천서해구문화재단",
            "aliases": ["인천서구문화재단"],
        }

        class Response:
            url = "https://www.seohae.go.kr/open_content/main/bbs/bbsMsgList.do?bcd=job&pgno=1"
            content = b"fixture"
            text = ""

        other_only = BeautifulSoup(
            """<html><title>채용소식</title><body>
            <h2>채용소식</h2>
            <a href="/open_content/main/bbs/bbsMsgDetail.do?bcd=job&msg_seq=6000">
              방사선실 기간제근로자 채용 공고
            </a>
            </body></html>""",
            "html.parser",
        )
        self.assertTrue(
            crawler.seohae_shared_board_zero_is_structurally_verified(
                other_only, foundation, Response()
            )
        )
        self.assertTrue(crawler.verify_board_surface(other_only, foundation, Response(), {}))

        missed_foundation = BeautifulSoup(
            """<html><title>채용소식</title><body>
            <h2>채용소식</h2>
            <div>2026년 제7회 (재)인천서해구문화재단 직원채용 공고</div>
            <a href="/open_content/main/bbs/bbsMsgDetail.do?bcd=job&msg_seq=5075">
              상세보기
            </a>
            </body></html>""",
            "html.parser",
        )
        self.assertFalse(
            crawler.seohae_shared_board_zero_is_structurally_verified(
                missed_foundation, foundation, Response()
            )
        )
        with self.assertRaisesRegex(RuntimeError, "no parseable details"):
            crawler.verify_board_surface(missed_foundation, foundation, Response(), {})

    def test_seohae_shared_board_zero_requires_exact_job_detail_contract(self):
        foundation = {
            "id": "incheon:seohae",
            "name": "인천서해구문화재단",
            "aliases": ["인천서구문화재단"],
        }

        class Response:
            url = "https://www.seohae.go.kr/open_content/main/bbs/bbsMsgList.do?bcd=job&pgno=1"
            content = b"fixture"
            text = ""

        malformed = BeautifulSoup(
            """<html><title>채용소식</title><body>
            <h2>채용소식</h2>
            <a href="/open_content/main/bbs/bbsMsgDetail.do?bcd=job">채용 공고</a>
            </body></html>""",
            "html.parser",
        )
        self.assertFalse(
            crawler.seohae_shared_board_zero_is_structurally_verified(
                malformed, foundation, Response()
            )
        )

    def test_hanam_municipal_board_requires_foundation_in_post_title(self):
        foundation={"id":"gyeonggi:hanam","name":"하남문화재단","aliases":["(재)하남문화재단"]}
        for title in ("시청 기간제근로자 채용 공고","하남시 직원 채용 공고"):
            self.assertFalse(crawler.candidate_belongs_to_foundation(foundation,title))
            self.assertFalse(reconcile.municipal_official_post_belongs_to_foundation({"title":title},foundation))
        title="하남문화재단 직원 채용 공고"
        self.assertTrue(crawler.candidate_belongs_to_foundation(foundation,title))
        self.assertTrue(reconcile.municipal_official_post_belongs_to_foundation({"title":title},foundation))

    def test_recent_official_post_without_deadline_has_bounded_visibility(self):
        today=unified.base.TODAY
        post={"province":"경기","sourceRole":"primary-official","detailLinkVerified":True,
              "transportVerified":True,"foundationRegistryId":"gyeonggi:gwacheon",
              "sourceIdentity":"official-foundation:gwacheon:test","url":"https://www.gcart.or.kr/recruitView.do?bbsIdx=1909",
              "title":"과천문화재단 직원 채용 공고","registered":today.isoformat(),"applyEnd":"",
              "deadlineVerification":"unverified-recent-official-post"}
        self.assertTrue(unified.foundation_official_current(post))
        self.assertFalse(unified.foundation_official_current({**post,"registered":(today-unified.timedelta(days=15)).isoformat()}))
        self.assertFalse(unified.foundation_official_current({**post,"deadlineVerification":""}))
        projected=unified.project_foundation_official(post)
        self.assertEqual(projected["deadlineVerification"],"unverified-recent-official-post")
        self.assertFalse(projected.get("applyEnd"))

    def test_navigation_and_hiring_disclosure_cannot_be_detail_jobs(self):
        board="https://www.gangnam.go.kr/office/gfac/board/gfac_staffrec/list.do?mid=gfac_staffRec"
        self.assertFalse(crawler.looks_like_detail_url(board,"https://www.gangnam.go.kr/office/gfac/board/gfac_chargeteacher/list.do?mid=gfac_chargeTeacher"))
        self.assertTrue(crawler.looks_like_detail_url(board,"https://www.gangnam.go.kr/office/gfac/board/gfac_staffrec/588/view.do?mid=gfac_staffRec"))
        self.assertFalse(crawler.official_position_title("2026년 제4차 재단 직원 공개채용 채용과정 공개"))

    def test_blocked_shell_and_script_links_do_not_prove_board_health(self):
        foundation={"id":"seoul:nowon","name":"노원문화재단","aliases":[]}
        class Response:
            url="https://nowonarts.kr/channels/job/posts"
            def __init__(self,markup):
                self.text=markup
                self.content=markup.encode()
        for markup in (
            "<html>노원문화재단 WELLCONN 접근 대기</html>",
            "<html>노원문화재단 채용 <div ng-repeat='job in jobs'>{{job.title}}</div></html>",
            "<html>노원문화재단 채용 <a href='javascript:reg_view(42)'>직원 채용 공고</a></html>",
        ):
            with self.assertRaises(RuntimeError):
                crawler.verify_board_surface(BeautifulSoup(markup,"html.parser"),foundation,Response(markup),{})

    def test_https_official_redirect_to_http_fails_closed(self):
        class Response:
            url="http://nowonarts.kr/channels/job/posts"
            encoding="utf-8"
            def raise_for_status(self): pass
        class Session:
            def get(self,*args,**kwargs): return Response()
        with self.assertRaisesRegex(RuntimeError,"downgraded"):
            crawler.resilient_request(Session(),"https://nowonarts.kr/channels/job/posts")

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

    def test_ifac_go_view_resolves_verified_official_detail(self):
        title="재단법인 인천문화재단 감사(비상임) 모집 공고(9.21.~10.6.)"
        anchor=BeautifulSoup(
            '<a href="#none" onclick="goView(\'236088\', \'\');"><dl class="title"><dd>'
            +title+'</dd></dl></a>',"html.parser").a
        board="https://ifac.or.kr/bbs/list.do?bbsCtgrySn=74&key=m2501152808232"
        self.assertTrue(crawler.official_position_title(title))
        self.assertEqual(crawler.ifac_detail_url(anchor,board),
                         "https://ifac.or.kr/bbs/view.do?bbsSn=236088&key=m2501152808232")
        self.assertEqual(crawler.ifac_title_deadline(title,crawler.base.date(2026,9,21)),
                         crawler.base.date(2026,10,6))
        anchor['onclick']="goView('../../bad', '');"
        self.assertIsNone(crawler.ifac_detail_url(anchor,board))


if __name__ == "__main__":
    unittest.main()
