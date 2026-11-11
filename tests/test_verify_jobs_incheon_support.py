import unittest

from scripts import verify_jobs


class VerifyJobsIncheonSupportTests(unittest.TestCase):
    def test_all_five_incheon_support_detail_contracts_are_exact(self):
        jobs = [
            {
                "province": "인천",
                "sourceType": "교육지원청 개별 게시판",
                "source": "인천남부교육지원청",
                "url": "https://nambu.ice.go.kr/common/Contents.do#5BgVJf/179/0gVhzY/BO/R/49535/N/N",
            },
            {
                "province": "인천",
                "sourceType": "교육지원청 개별 게시판",
                "source": "인천북부교육지원청",
                "url": "https://bukbu.ice.go.kr/bbs/data/view.do?bbs_mst_idx=BM0000000049&data_idx=BD0000008176&menu_idx=86",
            },
            {
                "province": "인천",
                "sourceType": "교육지원청 개별 게시판",
                "source": "인천동부교육지원청",
                "url": "https://dongbu.ice.go.kr/bbs/bbsMsgDetail.do?bcd=job_offer&msg_seq=6928",
            },
            {
                "province": "인천",
                "sourceType": "교육지원청 개별 게시판",
                "source": "인천서부교육지원청",
                "url": "https://seobu.ice.go.kr/bseobu/read.aspx?board_idx=159256&page=1&board_code=4674&g1=",
            },
            {
                "province": "인천",
                "sourceType": "교육지원청 개별 게시판",
                "source": "인천강화교육지원청",
                "url": "https://ganghwa.ice.go.kr/open/recruiting.asp?num=4220&ptype=view&cmode=mc&cstep=0302000000&path_url=%2Fopen%2Frecruiting.asp&pNum=4221&nNum=4219",
            },
        ]
        result = verify_jobs.exact_support_link_issues(jobs)
        self.assertEqual(result["total"], 5)
        self.assertEqual(result["resolved"], 5)
        self.assertEqual(result["unresolved"], 0)

    def test_incheon_list_page_is_not_accepted_as_detail(self):
        jobs = [{
            "province": "인천",
            "sourceType": "교육지원청 개별 게시판",
            "source": "인천서부교육지원청",
            "url": "https://seobu.ice.go.kr/bseobu/list.aspx?board_code=4674",
        }]
        result = verify_jobs.exact_support_link_issues(jobs)
        self.assertEqual(result["resolved"], 0)
        self.assertEqual(result["unresolved"], 1)

    def test_support_issue_scan_includes_incheon(self):
        data = {
            "sources": {
                "gyeonggi": {"supportOffices": []},
                "seoul": {"supportOffices": []},
                "incheon": {"supportOffices": [
                    {"name": "인천남부교육지원청", "ok": False, "state": "error", "message": "test"}
                ]},
            }
        }
        issues = verify_jobs.support_issues(data)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["name"], "인천남부교육지원청")


if __name__ == "__main__":
    unittest.main()
