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
        self.assertIn("cat=3", rows["incheon:yeonsu"]["officialRecruitmentUrl"])
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

    def test_dongjak_official_mirror_filters_other_foundations_per_post(self):
        foundation = {"id": "seoul:dongjak", "name": "동작문화재단", "aliases": []}
        self.assertTrue(crawler.candidate_belongs_to_foundation(
            foundation, "[동작문화재단] 2026 직원 채용", shared_board=True
        ))
        self.assertFalse(crawler.candidate_belongs_to_foundation(
            foundation, "[용산문화재단] 2026 직원 채용", shared_board=True
        ))

    def test_shared_municipal_boards_require_foundation_identity(self):
        cases = [
            ("seoul:guro", "구로문화재단", "구로구청 일반임기제 채용 공고"),
            ("gyeonggi:guri", "구리문화재단", "구리시 기간제근로자 채용 공고"),
            ("gyeonggi:hanam", "하남문화재단", "하남시 지방임기제공무원 채용 공고"),
            ("gyeonggi:seongnam", "성남문화재단", "성남시 기간제근로자 채용 공고"),
        ]
        for fid, name, unrelated in cases:
            foundation = {"id": fid, "name": name, "aliases": [f"(재){name}"]}
            self.assertTrue(
                crawler.candidate_belongs_to_foundation(
                    foundation, f"2026년 {name} 직원 채용 공고"
                )
            )
            self.assertFalse(crawler.candidate_belongs_to_foundation(foundation, unrelated))

    def test_foundation_owned_host_is_only_supporting_evidence(self):
        foundation = {
            "id": "seoul:seongdong",
            "name": "성동문화재단",
            "homepage": "https://www.sdfac.or.kr/",
        }
        self.assertTrue(
            crawler.foundation_owned_board_host(
                foundation,
                "https://www.sdfac.or.kr/kor/recruit/board/rctdata_list.do?gotoMenuNo",
            )
        )
        html = "<html><body>채용 공고 <a href='/jobs/23'>직원 채용</a></body></html>"
        response = SimpleNamespace(url="https://www.sdfac.or.kr/recruit", text=html, content=html.encode())
        with self.assertRaisesRegex(RuntimeError, "identity unproved"):
            crawler.verify_board_surface(BeautifulSoup(html, "html.parser"), foundation, response, {"/jobs/23": {}})
        shared = {
            "id": "gyeonggi:seongnam",
            "name": "성남문화재단",
            "homepage": "https://www.seongnam.go.kr/",
        }
        self.assertFalse(
            crawler.foundation_owned_board_host(shared, "https://www.seongnam.go.kr/bbs010402")
        )

    def test_blocked_js_shell_and_js_detail_pages_fail_closed(self):
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

    def test_stale_js_only_board_can_be_healthy_but_recent_js_fails(self):
        foundation = {
            "id": "seoul:dongdaemun",
            "name": "동대문문화재단",
            "aliases": ["(재)동대문문화재단"],
        }
        today = crawler.datetime.now(crawler.KST).date()
        stale_date = (today - crawler.base.timedelta(days=121)).isoformat()
        recent_date = (today - crawler.base.timedelta(days=9)).isoformat()
        stale_html = f"""
        <html><head><title>동대문문화재단 인재채용</title></head><body>
          <div>{stale_date} <a href="javascript:view(224)">2026년 제2차 동대문문화재단 직원 채용 공고</a></div>
        </body></html>
        """
        stale_response = SimpleNamespace(
            url="https://ddmac.or.kr/sub04/sub03.php",
            text=stale_html,
            content=stale_html.encode(),
        )
        self.assertTrue(
            crawler.verify_board_surface(
                BeautifulSoup(stale_html, "html.parser"),
                foundation,
                stale_response,
                {},
            )
        )

        recent_html = f"""
        <html><head><title>동대문문화재단 인재채용</title></head><body>
          <div>{recent_date} <a href="javascript:view(225)">2026년 제3차 동대문문화재단 직원 채용 공고</a></div>
        </body></html>
        """
        recent_response = SimpleNamespace(
            url="https://ddmac.or.kr/sub04/sub03.php",
            text=recent_html,
            content=recent_html.encode(),
        )
        with self.assertRaisesRegex(RuntimeError, "unsupported JavaScript"):
            crawler.verify_board_surface(
                BeautifulSoup(recent_html, "html.parser"),
                foundation,
                recent_response,
                {},
            )

    def test_https_redirect_to_http_fails(self):
        response = SimpleNamespace(url="http://ypcf.or.kr/recruit", encoding="utf-8", raise_for_status=lambda: None)
        session = SimpleNamespace(get=lambda *args, **kwargs: response)
        with self.assertRaisesRegex(RuntimeError, "downgraded"):
            crawler.resilient_request(session, "https://ypcf.or.kr/recruit")

    def test_designated_saramin_ending_page_is_explicit_zero(self):
        foundation = {"id": "gyeonggi:anyang", "name": "안양문화예술재단", "aliases": []}
        response = SimpleNamespace(
            url="https://ayac.saramin.co.kr/ending_page.html",
            text="<html><body><img alt='채용 종료'></body></html>",
            content=b"x",
            encoding="utf-8",
        )
        with patch.object(crawler, "resilient_request", return_value=response):
            jobs, meta = crawler.designated_saramin_rows(
                None, foundation, "https://ayac.saramin.co.kr/"
            )
        self.assertEqual(jobs, [])
        self.assertTrue(meta["explicitEmpty"])
        self.assertEqual(meta["evidence"], "saramin-ending-page")

    def test_secondary_sfac_board_requires_explicit_empty_text(self):
        response = SimpleNamespace(url="https://sfac.careerlink.kr/", status_code=200,
                                   text="<html><body>서울문화재단 채용</body></html>")
        with patch.object(crawler, "resilient_request", return_value=response):
            with self.assertRaisesRegex(RuntimeError, "lacks an explicit empty state"):
                crawler.sfac_careerlink_probe(None)

    def test_saas_empty_states_and_modern_incruit_job_cards(self):
        self.assertTrue(crawler.EXPLICIT_EMPTY_RE.search("등록된 정보가 없습니다."))
        self.assertTrue(crawler.EXPLICIT_EMPTY_RE.search("등록된 채용공고가 없습니다."))
        self.assertTrue(crawler.EXPLICIT_EMPTY_RE.search("진행 중 채용공고 0건"))
        self.assertFalse(crawler.official_position_title("진행 중 채용공고 0건"))

        foundation = {
            "id": "gyeonggi:metropolitan",
            "name": "경기문화재단",
            "aliases": ["(재)경기문화재단", "재단법인 경기문화재단"],
        }
        html = """
        <html><head><title>(재)경기문화재단 채용리스트</title></head><body>
          <div class="job-card">
            모집중 2026.09.07 09:00~2026.10.14 15:00
            2026년 경기문화재단 제10차 기간제 근로자 채용
            <a href="/ggcf/job/2609030002">자세히 보기</a>
          </div>
        </body></html>
        """
        response = SimpleNamespace(
            url="https://recruit.incruit.com/ggcf/job/",
            text=html,
            content=html.encode(),
        )
        with patch.object(crawler, "resilient_request", return_value=response) as request:
            _, soup, candidates, dated = crawler.list_detail_candidates(
                None, foundation, "https://recruit.incruit.com/ggcf/"
            )
        request.assert_called_once_with(None, "https://recruit.incruit.com/ggcf/job/")
        self.assertEqual(len(candidates), 1)
        self.assertEqual(dated, 1)
        candidate = next(iter(candidates.values()))
        self.assertEqual(candidate["url"], "https://recruit.incruit.com/ggcf/job/2609030002")
        self.assertEqual(candidate["fallbackTitle"], "")
        self.assertTrue(crawler.verify_board_surface(soup, foundation, response, candidates))

        empty_html = """
        <html><head><title>(재)성북문화재단 채용리스트</title></head>
        <body><h2>채용정보</h2><p>등록된 정보가 없습니다.</p></body></html>
        """
        empty_response = SimpleNamespace(
            url="https://recruit.incruit.com/sbculture/job/",
            text=empty_html,
            content=empty_html.encode(),
        )
        empty_foundation = {
            "id": "seoul:seongbuk",
            "name": "성북문화재단",
            "aliases": ["(재)성북문화재단"],
        }
        self.assertTrue(
            crawler.verify_board_surface(
                BeautifulSoup(empty_html, "html.parser"),
                empty_foundation,
                empty_response,
                {},
            )
        )

    def test_explicit_zero_saas_state_short_circuits_navigation_links(self):
        cases = [
            (
                {"id": "gyeonggi:hwaseong", "name": "화성시문화관광재단", "aliases": []},
                "https://recruit.incruit.com/hcf/",
                "https://recruit.incruit.com/hcf/job/",
                "<html><body>진행중인 채용공고가 없습니다. <a href='/hcf/job/'>채용공고</a></body></html>",
            ),
            (
                {"id": "seoul:gangbuk", "name": "강북문화재단", "aliases": []},
                "https://gbcf.fairyhr.com/",
                "https://gbcf.fairyhr.com/",
                "<html><body>강북문화재단 진행 중 채용공고 0건 <a href='/announcement'>채용공고</a></body></html>",
            ),
        ]
        for foundation, requested, final_url, html in cases:
            response = SimpleNamespace(url=final_url, text=html, content=html.encode())
            with self.subTest(requested=requested), patch.object(
                crawler, "resilient_request", return_value=response
            ) as request:
                _, _, candidates, dated = crawler.list_detail_candidates(
                    None, foundation, requested
                )
            self.assertEqual(candidates, {})
            self.assertEqual(dated, 0)
            expected = (
                "https://recruit.incruit.com/hcf/job/"
                if "recruit.incruit.com" in requested
                else requested
            )
            request.assert_called_once_with(None, expected)

    def test_explicit_zero_count_allows_spacing(self):
        self.assertRegex(
            "진행 중 채용공고 0 건",
            crawler.EXPLICIT_EMPTY_RE,
        )

    def test_list_deadline_can_close_stale_candidate_before_detail_fetch(self):
        today = crawler.base.date(2026, 10, 1)
        registered = crawler.base.date(2026, 8, 7)
        context = "2026-08-07 ~ 2026-08-18 마감"
        apply_end = crawler.base.extract_apply_end(context, registered)
        self.assertEqual(apply_end, crawler.base.date(2026, 8, 18))
        self.assertLess(apply_end, today)

    def test_recent_post_without_deadline_is_not_verified_open(self):
        today = crawler.base.date(2026, 9, 27)
        self.assertFalse(crawler.verified_open_deadline(crawler.base.date(2026, 9, 15), None, today))
        self.assertFalse(crawler.verified_open_deadline(crawler.base.date(2026, 9, 15), crawler.base.date(2026, 9, 26), today))
        self.assertTrue(crawler.verified_open_deadline(crawler.base.date(2026, 9, 15), crawler.base.date(2026, 10, 1), today))

    def test_ifac_go_view_uses_exact_official_detail_and_title_period(self):
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

    def test_gwangjin_uses_verified_official_mirror_for_5xx_primary(self):
        rows = {x["id"]: x for x in self.registry["institutions"]}
        row = rows["seoul:gwangjin"]
        self.assertIn("naruart.applyin.co.kr", row["officialRecruitmentUrl"])
        self.assertIn("gwangjin.go.kr/portal/bbs/B0000004/list.do", row["verifiedFallbackRecruitmentUrl"])
        self.assertEqual(row["verifiedFallbackRole"], "secondary-official-mirror")
        self.assertIn("seoul:gwangjin", crawler.SHARED_OFFICIAL_BOARD_FOUNDATION_IDS)

    def test_paju_prefers_foundation_owned_official_board(self):
        rows = {x["id"]: x for x in self.registry["institutions"]}
        self.assertIn("pajucf.or.kr/community/notice.php", rows["gyeonggi:paju"]["officialRecruitmentUrl"])
        self.assertNotIn("gyeonggi:paju", crawler.SHARED_OFFICIAL_BOARD_FOUNDATION_IDS)
        self.assertIn("pajucf.or.kr", crawler.GENERIC_OFFICIAL_HOSTS)

    def test_dongjak_uses_filtered_seoul_culture_official_mirror(self):
        rows = {x["id"]: x for x in self.registry["institutions"]}
        row = rows["seoul:dongjak"]
        self.assertIn("culture.seoul.go.kr/culture/bbs/B0000002/list.do", row["verifiedFallbackRecruitmentUrl"])
        self.assertIn("searchCnd=1", row["verifiedFallbackRecruitmentUrl"])
        self.assertIn("searchWrd=", row["verifiedFallbackRecruitmentUrl"])
        self.assertEqual(row["verifiedFallbackRole"], "secondary-official-mirror")
        self.assertIn("seoul:dongjak", crawler.SHARED_OFFICIAL_BOARD_FOUNDATION_IDS)

    def test_bucheon_uses_verified_city_recruitment_mirror(self):
        rows = {x["id"]: x for x in self.registry["institutions"]}
        row = rows["gyeonggi:bucheon"]
        self.assertIn("bucheon.go.kr/site/program/board/basicboard/list", row["officialRecruitmentUrl"])
        self.assertNotIn("verifiedFallbackRecruitmentUrl", row)
        self.assertIn("gyeonggi:bucheon", crawler.SHARED_OFFICIAL_BOARD_FOUNDATION_IDS)
        self.assertIn("bucheon.go.kr", crawler.GENERIC_OFFICIAL_HOSTS)
        url = "https://www.bucheon.go.kr/site/program/board/basicboard/view?boardtypeid=26756&encid=BZJJFP82CPkJg4%2BYB5twEA%3D%3D"
        self.assertTrue(crawler.detail_identity(url).startswith("encid:"))

    def test_seocho_uses_applyin_public_jobs_contract(self):
        from pathlib import Path
        rows = {x["id"]: x for x in self.registry["institutions"]}
        url = rows["seoul:seocho"]["officialRecruitmentUrl"]
        self.assertEqual(url, "https://seochocf.applyin.co.kr/")
        source = Path("scripts/crawl_official_foundation_jobs_v2.py").read_text(encoding="utf-8")
        self.assertIn("def applyin_rows", source)
        self.assertIn('"applyin-public-jobs-v1"', source)
        self.assertIn('"jobs.show"', source)
        self.assertIn('extra_headers={"Accept":"application/json"}', source)
        self.assertIn('"naruart.applyin.co.kr"', source)

    def test_jungnang_uses_ninehire_public_recruitment_contract(self):
        from pathlib import Path
        rows = {x["id"]: x for x in self.registry["institutions"]}
        self.assertEqual(rows["seoul:jungnang"]["officialRecruitmentUrl"], "https://recruit.jnfac.or.kr/")
        source = Path("scripts/crawl_official_foundation_jobs_v2.py").read_text(encoding="utf-8")
        self.assertIn("def ninehire_rows", source)
        self.assertIn("https://api.ninehire.com/identity-access/homepage/recruitments", source)
        self.assertIn('"countPerPage":100', source)
        self.assertIn('"explicitEmpty":True', source)

    def test_transport_fallbacks_are_explicit_and_bounded(self):
        rows = {x["id"]: x for x in self.registry["institutions"]}
        self.assertIn("culture.seoul.go.kr", rows["seoul:dongjak"]["verifiedFallbackRecruitmentUrl"])
        self.assertEqual(rows["seoul:dongjak"]["verifiedFallbackRole"], "secondary-official-mirror")
        self.assertNotIn("verifiedFallbackRecruitmentUrl", rows["gyeonggi:seongnam"])
        self.assertIn("gm.go.kr/pt/user/bbs/BD_selectBbsList.do", rows["gyeonggi:gwangmyeong"]["officialRecruitmentUrl"])
        self.assertIn("q_searchVal=", rows["gyeonggi:gwangmyeong"]["officialRecruitmentUrl"])
        self.assertIn("goyang.go.kr/jobs", rows["gyeonggi:goyang"]["officialRecruitmentUrl"])
        self.assertIn("q_searchVal=", rows["gyeonggi:goyang"]["officialRecruitmentUrl"])
        self.assertIn("ayac.saramin.co.kr", rows["gyeonggi:anyang"]["officialRecruitmentUrl"])
        self.assertIn("yfac.kr/main/contents.do", rows["seoul:yangcheon"]["officialRecruitmentUrl"])
        self.assertIn("ydpcf.or.kr/board.do", rows["seoul:yeongdeungpo"]["officialRecruitmentUrl"])
        self.assertIn("goyang.go.kr", crawler.GENERIC_OFFICIAL_HOSTS)
        self.assertIn("gm.go.kr", crawler.GENERIC_OFFICIAL_HOSTS)
        self.assertIn("gyeonggi:goyang", crawler.SHARED_OFFICIAL_BOARD_FOUNDATION_IDS)
        self.assertIn("gyeonggi:gwangmyeong", crawler.SHARED_OFFICIAL_BOARD_FOUNDATION_IDS)
        self.assertIn("yfac.fairyhr.com", crawler.GENERIC_OFFICIAL_HOSTS)
        self.assertIn("seoul:dongjak", crawler.SHARED_OFFICIAL_BOARD_FOUNDATION_IDS)

    def test_position_scope_includes_foundation_front_of_house_staff(self):
        self.assertTrue(
            crawler.official_position_title("2026년 3차 구리문화재단 공연장 안내원 추가 모집")
        )

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
            "2026년 제4차 재단 직원 공개채용 채용과정 공개",
            "직원채용공고",
            "지도강사 모집공고",
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

    def test_ninehire_root_uses_recruit_surface_and_explicit_empty(self):
        foundation = {"id": "seoul:jungnang", "name": "중랑문화재단", "aliases": ["재단법인 중랑문화재단"]}
        html = "<html><body>재단법인 중랑문화재단 채용 공고 진행 중인 채용이 없습니다.</body></html>"
        response = SimpleNamespace(
            url="https://recruit.jnfac.or.kr/recruit",
            text=html,
            content=html.encode(),
        )
        with patch.object(crawler, "resilient_request", return_value=response) as request:
            _, soup, candidates, dated = crawler.list_detail_candidates(
                None, foundation, "https://recruit.jnfac.or.kr/"
            )
        request.assert_called_once_with(None, "https://recruit.jnfac.or.kr/recruit")
        self.assertEqual(candidates, {})
        self.assertEqual(dated, 0)
        self.assertTrue(crawler.verify_board_surface(soup, foundation, response, candidates))

    def test_named_municipal_javascript_detail_contracts_use_second_identifier(self):
        goyang = BeautifulSoup(
            """<a href="#" onclick="fnView('1082','20260903101529704','/jobs','-1','1','');">(재)고양문화재단 비상임감사 공개모집공고</a>""",
            "html.parser",
        ).find("a")
        resolved = crawler.official_js_detail_url(
            goyang,
            "https://www.goyang.go.kr/jobs/user/bbs/BD_selectBbsList.do?q_bbsCode=1082",
        )
        self.assertIn("q_bbsCode=1082", resolved)
        self.assertIn("q_bbscttSn=20260903101529704", resolved)

        paju = BeautifulSoup(
            """<a href="javascript:void(0)" onclick="jsView('1022', '20260930094802200', 'N', 'Y'); return false;">파주 채용 공고</a>""",
            "html.parser",
        ).find("a")
        resolved = crawler.official_js_detail_url(
            paju,
            "https://www.paju.go.kr/user/board/BD_board.list.do?bbsCd=1022&q_ctgCd=4064",
        )
        self.assertIn("bbsCd=1022", resolved)
        self.assertIn("seq=20260930094802200", resolved)
        self.assertIn("q_ctgCd=4064", resolved)

    def test_observed_foundation_javascript_contracts_resolve_exact_details(self):
        geumcheon = BeautifulSoup(
            """<tr onclick="goBoardView('9325');"><td class="title"><a href="javascript:void(0);">(재)금천문화재단 직원 공개모집 공고</a></td></tr>""",
            "html.parser",
        ).find("a")
        resolved = crawler.official_js_detail_url(
            geumcheon,
            "https://gcfac.or.kr/board/recruit?gcfac_menu_cd=U0140",
        )
        self.assertIn("/board/recruitDetail?", resolved)
        self.assertIn("board_seq=9325", resolved)

        mapo = BeautifulSoup(
            """<a class="btnDetail" href="javascript:void(0);" seq="9169">2026년 제5회 마포문화재단 직원 채용 공고</a>""",
            "html.parser",
        ).find("a")
        resolved = crawler.official_js_detail_url(
            mapo,
            "https://www.mfac.or.kr/communication/notice_all_list.jsp?sc_type=3",
        )
        self.assertIn("/communication/notice_all_view.jsp?", resolved)
        self.assertIn("pk_seq=9169", resolved)

        pocheon = BeautifulSoup(
            """<a href="javascript:reg_view('1819123')">(재)포천문화관광재단 2026년 제5회 직원 공개채용 공고</a>""",
            "html.parser",
        ).find("a")
        resolved = crawler.official_js_detail_url(
            pocheon,
            "https://www.pcfac.or.kr/sub07/sub03.php",
        )
        self.assertIn("/sub07/sub03.php?", resolved)
        self.assertIn("type=view", resolved)
        self.assertIn("uid=1819123", resolved)

    def test_known_javascript_detail_contracts_parse_without_regex_errors(self):
        cases = [
            (
                "https://www.goyang.go.kr/jobs/user/bbs/BD_selectBbsList.do?q_bbsCode=1082",
                '<a href="javascript:void(0);" onclick="fn_view(1234567890)">고양문화재단 직원 채용</a>',
                "q_bbscttSn=1234567890",
            ),
            (
                "https://gcfac.or.kr/board/recruit?gcfac_menu_cd=U0140",
                '<a href="javascript:void(0);" onclick="view(1234)">금천문화재단 직원 채용</a>',
                "board_seq=1234",
            ),
            (
                "https://www.mfac.or.kr/communication/notice_all_list.jsp?sc_type=3",
                '<a href="javascript:void(0);" onclick="goView(1234)">마포문화재단 직원 채용</a>',
                "pk_seq=1234",
            ),
            (
                "https://www.pccf.or.kr/bbs/list.do?key=2603120031",
                '<a href="javascript:void(0);" onclick="view(123456)">평택시문화재단 직원 채용</a>',
                "pstSn=123456",
            ),
            (
                "https://www.paju.go.kr/user/board/BD_board.list.do?bbsCd=1022&q_ctgCd=4064",
                '<a href="javascript:void(0);" onclick="view(1234567890)">파주문화재단 직원 채용</a>',
                "seq=1234567890",
            ),
        ]
        for board_url, html, expected in cases:
            anchor = BeautifulSoup(html, "html.parser").find("a")
            resolved = crawler.official_js_detail_url(anchor, board_url)
            self.assertIsNotNone(resolved, board_url)
            self.assertIn(expected, resolved, board_url)

    def test_recruitment_result_notice_is_not_an_open_position(self):
        self.assertFalse(
            crawler.official_position_title(
                "(재)금천문화재단 제6대 임원(이사장,대표이사) 공개모집 결과 공고"
            )
        )

    def test_dbfac_ajax_rows_pair_recruitment_with_later_stage(self):
        soup = BeautifulSoup(
            """<table>
            <tr><td><a href="javascript:contentsViewAll('caf299857022408fbcbfff2375dc5e5f','7')">[채용] [제2026-04호] 도봉문화재단 기간제근로자 채용 공고</a></td><td>2026-09-10</td></tr>
            <tr><td><a href="javascript:contentsViewAll('84288269650f42f8bf38f69c2011a27b','7')">[발표] [제2026-04호] 도봉문화재단 기간제근로자 채용 서류전형 합격자 발표 및 면접전형 안내</a></td><td>2026-09-28</td></tr>
            </table>""",
            "html.parser",
        )
        rows = crawler.dbfac_list_rows(soup)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["noticeKey"], "2026-4")
        self.assertFalse(rows[0]["resultLike"])
        self.assertTrue(rows[1]["resultLike"])
        self.assertGreater(rows[1]["registered"], rows[0]["registered"])

    def test_vue_recruitment_filters_use_verified_category_contracts(self):
        gangdong = crawler.vue_notice_filter(17, 1)
        junggu = crawler.vue_notice_filter(19, 2)
        self.assertEqual(gangdong["CategoryID"], 17)
        self.assertEqual(gangdong["DepartmentID"], 1)
        self.assertEqual(gangdong["PageSize"], 30)
        self.assertEqual(junggu["CategoryID"], 19)
        self.assertEqual(junggu["PageIndex"], 2)

    def test_efac_closed_row_contract_is_explicit(self):
        soup = BeautifulSoup(
            """<table><tr class="list" onclick="reg_view('5098')">
            <td><span>마감</span></td><td>(재)은평문화재단 2026년 제2회 직원 채용 공고</td>
            <td>은평문화재단</td><td>4,017</td><td>2026-05-28</td></tr></table>""",
            "html.parser",
        )
        rows = crawler.efac_list_rows(soup)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["uid"], "5098")
        self.assertTrue(rows[0]["closed"])
        self.assertEqual(rows[0]["registered"], crawler.base.date(2026, 5, 28))

    def test_native_detail_identity_prefers_query_id(self):
        self.assertEqual(
            crawler.detail_identity("https://recruit.efac.or.kr/sub01/sub01.php?type=view&uid=5098"),
            "uid:5098",
        )
        self.assertTrue(crawler.looks_like_detail_url(
            "https://recruit.efac.or.kr/sub01/sub01.php",
            "https://recruit.efac.or.kr/sub01/sub01.php?type=view&uid=5098",
        ))
        self.assertEqual(
            crawler.detail_identity("https://www.jcf.or.kr/main/bbs/bbsMsgDetail.do?bcd=recruit&msg_seq=118"),
            "msg_seq:118",
        )
        self.assertEqual(
            crawler.detail_identity("https://www.bpcf.or.kr/bpcf/bbs/BMSR00001/view.do?boardId=13000&menuNo=200059"),
            "boardId:13000",
        )

    def test_observed_official_detail_query_contracts_are_specific(self):
        cases = [
            (
                "https://www.guri.go.kr/www/selectBbsNttList.do?bbsNo=41&key=389",
                "https://www.guri.go.kr/www/selectBbsNttView.do?bbsNo=41&key=389&nttNo=146597&pageIndex=1",
                "nttNo:146597",
            ),
            (
                "https://www.nyjcf.or.kr/www/25",
                "https://www.nyjcf.or.kr/www/25?action=read&action-value=38119bc1c9df4b61e8ce45b9ceef28fe",
                "action-value:38119bc1c9df4b61e8ce45b9ceef28fe",
            ),
            (
                "https://www.yjcf.or.kr/brd/board/217/L/menu/342",
                "https://www.yjcf.or.kr/brd/board/217/L/menu/342?bbIdx=2504&brdType=R&thisPage=1",
                "bbIdx:2504",
            ),
        ]
        for board_url, detail_url, expected_identity in cases:
            self.assertTrue(crawler.looks_like_detail_url(board_url, detail_url), detail_url)
            self.assertEqual(crawler.detail_identity(detail_url), expected_identity)

    def test_board_navigation_cannot_be_published_as_detail(self):
        self.assertFalse(crawler.official_position_title("채용공고"))
        self.assertFalse(crawler.looks_like_detail_url(
            "https://www.swcf.or.kr/?p=116", "https://www.swcf.or.kr/?p=116&bxPage=1"))
        self.assertFalse(crawler.looks_like_detail_url(
            "https://www.ydpcf.or.kr/board.do?bid=3&p=1", "https://www.ydpcf.or.kr/board.do?bid=3"))
        self.assertTrue(crawler.looks_like_detail_url(
            "https://ypcf.or.kr/recruit", "https://ypcf.or.kr/recruit/?bmode=view&idx=174131299"))


if __name__ == "__main__":
    unittest.main()
