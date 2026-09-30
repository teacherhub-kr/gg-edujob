import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import complete_support_coverage as coverage
import seoul_support_detail_metadata as detail


class Response:
    encoding = "utf-8"
    apparent_encoding = "utf-8"

    def __init__(self, html):
        self.text = html

    def raise_for_status(self):
        return None


class Session:
    def __init__(self, html):
        self.html = html

    def post(self, *args, **kwargs):
        return Response(self.html)


class SeoulSupportExactDetailTests(unittest.TestCase):
    def test_exact_registration_requires_matching_official_identity(self):
        html = """
        <table>
          <tr><th>등록일자</th><td>2026-09-30</td><th>마감일자</th><td>2026-10-03</td></tr>
          <tr><th>기관명</th><td>서울어울초등학교</td></tr>
        </table>
        """
        board = "https://sbedu.sen.go.kr/FUS/JO/JOL11.do"
        self.assertEqual(
            detail.exact_registration_from_detail(
                Session(html), board, "5592", "서울어울초등학교", "2026-10-03"
            ),
            "2026/09/30",
        )
        self.assertEqual(
            detail.exact_registration_from_detail(
                Session(html), board, "5592", "다른학교", "2026-10-03"
            ),
            "",
        )
        self.assertEqual(
            detail.exact_registration_from_detail(
                Session(html), board, "5592", "서울어울초등학교", "2026-10-04"
            ),
            "",
        )

    def test_list_uses_subject_anchor_and_exact_detail_date(self):
        board = "https://sbedu.sen.go.kr/FUS/JO/JOL11.do"
        html = """
        <table>
          <tr><th>기관명</th><th>분야(과목)</th><th>마감일</th></tr>
          <tr>
            <td><a href="javascript:fncDetailView('5592');">서울어울초등학교</a></td>
            <td><a href="javascript:fncDetailView('5592');">초등예술하나 연극 강사</a></td>
            <td>2026-10-03</td>
          </tr>
        </table>
        """
        with patch.object(detail, "exact_registration_from_detail", return_value="2026/09/30") as fetch:
            rows, dates, expected, candidates, incomplete = coverage.seoul_items(
                BeautifulSoup(html, "html.parser"), board, {}
            )
        self.assertTrue(expected)
        self.assertEqual(candidates, 1)
        self.assertEqual(incomplete, 0)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1], "초등예술하나 연극 강사")
        self.assertEqual(dates, ["2026/09/30"])
        fetch.assert_called_once()

    def test_unproved_missing_date_stays_fail_closed(self):
        board = "https://sbedu.sen.go.kr/FUS/JO/JOL11.do"
        html = """
        <table>
          <tr><th>기관명</th><th>분야(과목)</th><th>마감일</th></tr>
          <tr>
            <td><a href="javascript:fncDetailView('5592');">서울어울초등학교</a></td>
            <td><a href="javascript:fncDetailView('5592');">초등예술하나 연극 강사</a></td>
            <td>2026-10-03</td>
          </tr>
        </table>
        """
        with patch.object(detail, "exact_registration_from_detail", return_value=""):
            rows, dates, expected, candidates, incomplete = coverage.seoul_items(
                BeautifulSoup(html, "html.parser"), board, {}
            )
        self.assertTrue(expected)
        self.assertEqual(candidates, 1)
        self.assertEqual(rows, [])
        self.assertEqual(dates, [])
        self.assertEqual(incomplete, 1)


if __name__ == "__main__":
    unittest.main()
