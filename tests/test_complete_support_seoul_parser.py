import sys
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.complete_support_coverage as c


def row(html):
    soup = BeautifulSoup(html, "html.parser")
    return soup, soup.table, soup.tbody.tr


def test_detail_anchor_beats_longer_school_anchor_and_maps_dates():
    soup, table, tr = row(
        """<table>
        <thead><tr><th>번호</th><th>학교명</th><th>제목</th><th>직종</th><th>등록일</th><th>마감일</th></tr></thead>
        <tbody><tr>
          <td>1</td>
          <td><a href="/school">아주아주긴학교기관명초등학교</a></td>
          <td><a href="#" onclick="fncDetailView('5593');">기간제교원 채용 공고</a></td>
          <td>기간제교원</td><td>2026.09.05</td><td>2026.09.10</td>
        </tr></tbody></table>"""
    )
    assert c.seoul_seq(tr) == "5593"
    anchor = c.seoul_detail_anchor_for_seq(tr, "5593")
    assert c.clean(anchor.get_text(" ", strip=True)) == "기간제교원 채용 공고"
    vals = c.seoul_row_values(table, tr)
    assert c.date_norm(c.first_of(vals, ["등록일", "작성일"])) == "2026/09/05"
    assert c.date_norm(c.first_of(vals, ["마감일", "접수마감일"])) == "2026/09/10"
    items, _, _, _, _ = c.seoul_items_from_soup(soup)
    assert items[0][1] == "기간제교원 채용 공고"
    assert items[0][2] == "2026/09/05"
    assert items[0][4] is True


def test_missing_registered_is_not_guessed_from_deadline():
    soup, _, _ = row(
        """<table>
        <thead><tr><th>학교명</th><th>제목</th><th>등록일</th><th>마감일</th></tr></thead>
        <tbody><tr>
          <td>서울어울초등학교</td>
          <td><a href="#" onclick="fncDetailView('5592');">초등예술하나 연극 강사(6학년)</a></td>
          <td></td><td>2026.10.03</td>
        </tr></tbody></table>"""
    )
    items, _, _, _, _ = c.seoul_items_from_soup(soup)
    assert items[0][0] == "5592"
    assert items[0][2] == ""


def test_known_malformed_rows_fail_closed():
    base = {
        "province": "서울",
        "sourceType": "교육지원청 개별 게시판",
        "id": "sen-complete-gdspedu.sen.go.kr-8312",
        "source": "강동송파교육지원청",
        "school": "서울버들초등학교",
        "title": "서울버들초등학교",
        "registered": "2026/09/04",
    }
    assert c.malformed_seoul_support_row(base) is True
    missing_date = dict(base, title="기간제교원 채용 공고", registered="")
    assert c.malformed_seoul_support_row(missing_date) is True
    valid = dict(base, title="기간제교원(음악) 채용 공고", registered="2026/09/19")
    assert c.malformed_seoul_support_row(valid) is False


if __name__ == "__main__":
    test_detail_anchor_beats_longer_school_anchor_and_maps_dates()
    test_missing_registered_is_not_guessed_from_deadline()
    test_known_malformed_rows_fail_closed()
    print("Seoul support completion parser regression verified")
