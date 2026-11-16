import unittest
from datetime import date

from scripts.probe_ice_all_board_index import exact_items, paging_submission


HTML = """
<html><body>
<form name="pagingForm" method="post" action="/ontong/na/ntt/selectAllNttList.do">
  <input name="currPage" value="1"><input name="searchType" value="">
  <input name="CSRFToken" value="secret-never-logged">
</form>
<table>
<tr><td>인천광역시교육청</td><td>채용공고</td>
<td><a href="/ice/na/ntt/selectNttInfo.do?bbsAllView=Y&amp;bbsId=1981&amp;mi=&amp;nttSn=3384055">채용</a></td>
<td>2026-11-08</td></tr>
<tr><td><a href="/ice/na/ntt/selectNttInfo.do?bbsId=1234&amp;nttSn=77">2026-12-31 일정 자료</a></td><td>2026.11.07</td></tr>
</table></body></html>
"""


class AllBoardProbeTest(unittest.TestCase):
    def test_official_iwee_mirror_is_allowlisted_for_read_only_proof(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parents[1] / "scripts" / "merge_incheon_official.py").read_text(encoding="utf-8")
        self.assertIn('"iwee.ice.go.kr"', source)

    def test_extracts_exact_official_identity_and_date(self):
        items = exact_items(HTML, "https://iwee.ice.go.kr/ontong/na/ntt/selectAllNttList.do")
        self.assertEqual({(x["bbsId"], x["nttSn"]) for x in items}, {("1981", "3384055"), ("1234", "77")})
        recruitment = next(x for x in items if x["bbsId"] == "1981")
        self.assertEqual(recruitment["posted"], date(2026, 11, 8))
        self.assertIn("nttSn=3384055", recruitment["url"])
        other = next(x for x in items if x["bbsId"] == "1234")
        self.assertEqual(other["posted"], date(2026, 11, 7))

    def test_rejects_non_official_host_and_non_numeric_identity(self):
        html = """<a href="https://example.com/ice/na/ntt/selectNttInfo.do?bbsId=1981&nttSn=1">x</a>
        <a href="/ice/na/ntt/selectNttInfo.do?bbsId=1981&nttSn=oops">y</a>"""
        self.assertEqual(exact_items(html, "https://iwee.ice.go.kr/"), [])

    def test_builds_bounded_page_two_form_without_exposing_values(self):
        target, fields, names = paging_submission(
            HTML, "https://iwee.ice.go.kr/ontong/na/ntt/selectAllNttList.do"
        )
        self.assertEqual(target, "https://iwee.ice.go.kr/ontong/na/ntt/selectAllNttList.do")
        self.assertIn(("currPage", "2"), fields)
        self.assertIn("CSRFToken", names)
        self.assertNotIn("secret-never-logged", repr(names))


if __name__ == "__main__":
    unittest.main()
