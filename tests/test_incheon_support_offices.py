import json
import unittest
from pathlib import Path

from scripts import collect_incheon_support as support
from scripts.source_registry import official_source_count
from scripts.stable_source_identity import canonical_source_id


class IncheonSupportOfficeTests(unittest.TestCase):
    def test_registry_contains_all_five_support_offices(self):
        data = json.loads(Path("sources.json").read_text(encoding="utf-8"))
        offices = data["incheon"]["supportOffices"]
        self.assertEqual(official_source_count(), 44)
        self.assertEqual(
            {item["key"] for item in offices},
            {"nambu", "bukbu", "dongbu", "seobu", "ganghwa"},
        )

    def test_support_native_identities_are_stable(self):
        north = {
            "province": "인천",
            "sourceType": "교육지원청 개별 게시판",
            "url": "https://bukbu.ice.go.kr/bbs/data/view.do?bbs_mst_idx=BM0000000049&data_idx=BD0000008173&menu_idx=86",
        }
        east = {
            "province": "인천",
            "sourceType": "교육지원청 개별 게시판",
            "url": "https://dongbu.ice.go.kr/bbs/bbsMsgDetail.do?bcd=job_offer&msg_seq=6928",
        }
        legacy = {
            "province": "인천",
            "sourceType": "교육지원청 개별 게시판",
            "url": "https://ganghwa.ice.go.kr/open/recruiting_view.asp?idx=3135",
        }
        self.assertEqual(
            canonical_source_id(north),
            "ice-support:bukbu.ice.go.kr:data_idx:BD0000008173",
        )
        self.assertEqual(
            canonical_source_id(east),
            "ice-support:dongbu.ice.go.kr:msg_seq:6928",
        )
        self.assertEqual(
            canonical_source_id(legacy),
            "ice-support:ganghwa.ice.go.kr:idx:3135",
        )

    def test_generic_table_parser_keeps_exact_detail_link(self):
        html = """
        <html><body>
        <table>
          <thead><tr><th>번호</th><th>기관명</th><th>제목</th><th>등록일</th><th>마감일</th></tr></thead>
          <tbody>
            <tr>
              <td>1</td><td>테스트중학교</td>
              <td><a href="/bbs/data/view.do?bbs_mst_idx=BM49&data_idx=BD123&menu_idx=86">기간제교원 채용 공고(음악)</a></td>
              <td>2026-09-19</td><td>2026-09-25</td>
            </tr>
          </tbody>
        </table>
        </body></html>
        """
        office = {
            "name": "인천북부교육지원청",
            "url": "https://bukbu.ice.go.kr/",
            "allowedHosts": ["bukbu.ice.go.kr"],
            "regions": [],
        }
        rows, meta = support.parse_support_page(
            html,
            "https://bukbu.ice.go.kr/bbs/data/list.do?bbs_mst_idx=BM49&menu_idx=86",
            office,
            90,
        )
        self.assertEqual(meta["rawRows"], 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["school"], "테스트중학교")
        self.assertEqual(rows[0]["type"], "기간제교원")
        self.assertEqual(rows[0]["registered"], "2026/09/19")
        self.assertEqual(
            rows[0]["url"],
            "https://bukbu.ice.go.kr/bbs/data/view.do?bbs_mst_idx=BM49&data_idx=BD123&menu_idx=86",
        )
        self.assertTrue(rows[0]["detailLinkResolved"])

    def test_cross_source_duplicate_keeps_support_identity(self):
        central = {
            "province": "인천",
            "school": "테스트중학교",
            "title": "기간제교원 채용 공고(음악)",
            "registered": "2026/09/19",
            "source": "인천광역시교육청 채용공고",
            "sourceType": "통합게시판",
            "bbsId": "1981",
            "nttSn": "999",
            "url": "https://www.ice.go.kr/ice/na/ntt/selectNttInfo.do?bbsId=1981&nttSn=999",
        }
        support_row = {
            "province": "인천",
            "school": "테스트중학교",
            "title": "기간제교원 채용 공고(음악)",
            "registered": "2026/09/19",
            "source": "인천북부교육지원청",
            "sourceType": "교육지원청 개별 게시판",
            "sourceNetwork": "incheon-support",
            "url": "https://bukbu.ice.go.kr/bbs/data/view.do?bbs_mst_idx=BM49&data_idx=BD123&menu_idx=86",
        }
        sid = canonical_source_id(support_row)
        payload = {"jobs": [central]}
        result = [{
            "office": {"name": "인천북부교육지원청"},
            "rows": [support_row],
            "status": {"name": "인천북부교육지원청"},
        }]
        added, collapsed = support.merge_support_rows(payload, result)
        self.assertEqual(added, 0)
        self.assertEqual(collapsed, 1)
        self.assertEqual(len(payload["jobs"]), 1)
        self.assertIn(sid, payload["jobs"][0]["sourceIdentities"])
        self.assertIn("인천북부교육지원청", payload["jobs"][0]["checkedSources"])


if __name__ == "__main__":
    unittest.main()
