"""A MirCMS final-page display must prove a full traversal, not an ignored page param."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import complete_support_coverage as c  # noqa: E402


BOARD = "https://www.goesh.kr/goesh/na/ntt/selectNttList.do?bbsId=5511&mi=9003"
SOURCE = {"name": "시흥교육지원청", "regions": ["시흥시"]}


def page_html(current, total, ntt, *, total_jobs="1,125", date="2026.11.10"):
    return (
        f"<div>전체 {total_jobs} 건 {current}/{total}페이지</div>"
        "<table><tr><th>번호</th><th>제목</th><th>등록일</th></tr>"
        f"<tr><td>{ntt}</td><td><a href=\"javascript:nttView('{ntt}')\">"
        "교육공무직 채용 공고</a></td>"
        f"<td>{date}</td></tr></table>"
    )


def simulate(board, src, responses):
    requested = []
    def fake_get(url, **kwargs):
        page = int(c.parse_qs(c.urlparse(url).query)["currPage"][0])
        requested.append(page)
        if page not in responses:
            raise AssertionError(f"unexpected request for page {page}")
        return SimpleNamespace(url=url, text=responses[page])
    with patch.object(c, "get", side_effect=fake_get), patch.object(c.time, "sleep", return_value=None):
        rows, meta = c.gyeonggi_board(board, src)
    return rows, meta, requested


class MirCMSLastPageTests(unittest.TestCase):
    def test_parser_accepts_official_numbered_total(self):
        self.assertEqual(c.published_pagination_marker("RSS 전체 1,125 건 1/113페이지"), (1, 113))
        self.assertEqual(c.published_pagination_marker("전체 940 건 93 / 94 페이지"), (93, 94))
        self.assertIsNone(c.published_pagination_marker("전체 1,125 건, 페이지 없음"))

    def test_final_numbered_page_proves_all_pages_even_with_recent_sticky_dates(self):
        rows, meta, requests = simulate(BOARD, SOURCE, {
            1: page_html(1, 2, 12345670),
            2: page_html(2, 2, 12345671),
        })
        self.assertEqual(requests, [1, 2])
        self.assertEqual(len(rows), 2)
        self.assertTrue(meta["naturalEnd"])
        self.assertFalse(meta["crossedLookback"])
        self.assertFalse(meta["paginationRepeated"])
        self.assertFalse(meta["paginationCounterMismatch"])
        self.assertTrue(meta["coverageComplete"])
        self.assertEqual(meta["declaredTotalPages"], 2)

    def test_server_ignoring_requested_page_fails_closed_even_with_distinct_rows(self):
        rows, meta, requests = simulate(BOARD, SOURCE, {
            1: page_html(1, 2, 12345670),
            2: page_html(1, 2, 12345671),
        })
        self.assertEqual(requests, [1, 2])
        self.assertFalse(meta["coverageComplete"])
        self.assertTrue(meta["paginationCounterMismatch"])
        self.assertFalse(meta["naturalEnd"])

    def test_page_total_changing_during_traversal_fails_closed(self):
        _, meta, requests = simulate(BOARD, SOURCE, {
            1: page_html(1, 2, 12345670),
            2: page_html(2, 3, 12345671),
        })
        self.assertEqual(requests, [1, 2])
        self.assertFalse(meta["coverageComplete"])
        self.assertTrue(meta["paginationCounterMismatch"])

    def test_unverified_last_page_without_counter_remains_incomplete(self):
        url = BOARD
        raw = (
            "<table><tr><th>제목</th><th>등록일</th></tr>"
            "<tr><td><a href=\"javascript:nttView('12345670')\">"
            "교육공무직 채용 공고</a></td><td>2026.11.10</td></tr></table>"
        )
        _, meta, requested = simulate(url, SOURCE, {1: raw, 2: raw})
        self.assertEqual(requested, [1, 2])
        self.assertTrue(meta["paginationRepeated"])
        self.assertFalse(meta["coverageComplete"])


if __name__ == "__main__":
    unittest.main()
