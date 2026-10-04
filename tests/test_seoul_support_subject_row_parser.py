import sys
import unittest
from bs4 import BeautifulSoup

sys.path.insert(0, "scripts")
import scrape_jobs as scraper
import complete_support_coverage as coverage


class SeoulSupportSubjectRowParserTests(unittest.TestCase):
    def row(self, field1, field2="-"):
        html = f"""
        <table>
          <thead><tr>
            <th>구분</th><th>학교명</th><th>분야1</th><th>분야2</th><th>등록일</th><th>마감일</th>
          </tr></thead>
          <tbody><tr>
            <td><a href='#' onclick="fncDetailView('15140');">기간제</a></td>
            <td>서울신은초등학교병설유치원</td>
            <td><a href='#' onclick="fncDetailView('15140');">{field1}</a></td>
            <td><a href='#' onclick="fncDetailView('15140');">{field2}</a></td>
            <td>2026.10.01</td><td>-</td>
          </tr></tbody>
        </table>
        """
        soup = BeautifulSoup(html, "html.parser")
        return soup, soup.table, soup.table.tbody.tr

    def test_placeholder_final_anchor_does_not_hide_field1(self):
        soup, table, tr = self.row("가을 단기방학 에듀케어 대체강사", "-")
        vals = scraper.seoul_row_values(table, tr)
        anchor = scraper.seoul_detail_anchor_for_seq(tr, "15140")
        self.assertEqual(scraper.clean(anchor.get_text(" ", strip=True)), "-")
        self.assertEqual(
            scraper.seoul_title_from_values(vals, anchor.get_text(" ", strip=True)),
            "가을 단기방학 에듀케어 대체강사",
        )
        self.assertEqual(scraper.seoul_subject_from_values(vals), "가을 단기방학 에듀케어 대체강사")

        items, dates, expected, candidates, incomplete = coverage.seoul_items(soup, "https://example.sen.go.kr/FUS/JO/JOL11.do", {})
        self.assertTrue(expected)
        self.assertEqual(candidates, 1)
        self.assertEqual(incomplete, 0)
        self.assertEqual(items[0][0], "15140")
        self.assertEqual(items[0][1], "가을 단기방학 에듀케어 대체강사")
        self.assertEqual(dates, ["2026/10/01"])

    def test_two_character_subject_is_valid(self):
        soup, table, tr = self.row("영어", "-")
        vals = scraper.seoul_row_values(table, tr)
        self.assertEqual(scraper.seoul_title_from_values(vals, "-"), "영어")
        self.assertEqual(scraper.seoul_subject_from_values(vals), "영어")
        items, _, _, _, incomplete = coverage.seoul_items(soup, "https://example.sen.go.kr/FUS/JO/JOL11.do", {})
        self.assertEqual(incomplete, 0)
        self.assertEqual(items[0][1], "영어")

    def test_second_real_subject_is_preserved(self):
        _, table, tr = self.row("6학년 영어", "기간제")
        vals = scraper.seoul_row_values(table, tr)
        self.assertEqual(scraper.seoul_title_from_values(vals, "기간제"), "6학년 영어 / 기간제")
        self.assertEqual(scraper.seoul_subject_from_values(vals), "6학년 영어 / 기간제")


if __name__ == "__main__":
    unittest.main()
