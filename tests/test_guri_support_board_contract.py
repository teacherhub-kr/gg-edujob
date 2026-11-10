"""Regression: Guri/Namyangju official recruitment menu, not unrelated cached pages.

The five canonical URLs are read from the official public menu. A previously
cached free/community board and office-internal boards are explicitly excluded
from the *recruitment* 90-day completeness contract.
"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import complete_support_coverage as c  # noqa: E402


GURI = "구리남양주교육지원청"
OFFICIAL = (
    ("8653", "16003"),  # 기간제교사
    ("8654", "14082"),  # 행정실무사
    ("8655", "14083"),  # 조리실무사
    ("8714", "14162"),  # 방과후강사
    ("8656", "14084"),  # 기타
)


class GuriMenuContractTests(unittest.TestCase):
    def get_source(self):
        return next(x for x in c.SOURCES["gyeonggi"]["supportOffices"] if x["name"] == GURI)

    def test_all_five_current_official_recruitment_categories_are_configured(self):
        src = self.get_source()
        self.assertEqual(len(src["boardUrls"]), 5)
        actual = []
        for url in src["boardUrls"]:
            q = c.parse_qs(c.urlparse(url).query)
            actual.append((q["bbsId"][0], q["mi"][0]))
            self.assertEqual(c.urlparse(url).hostname, "www.goegn.kr")
        self.assertEqual(tuple(actual), OFFICIAL)

    def test_old_miscached_community_and_internal_pages_cannot_gate_recruitment(self):
        src = self.get_source()
        stale = [
            "https://www.goegn.kr/goegn/na/ntt/selectNttList.do?bbsId=8653&mi=14162",
            "https://www.goegn.kr/goegn/na/ntt/selectNttList.do?bbsId=8653&mi=14084",
            "https://www.goegn.kr/goegn/na/ntt/selectNttList.do?mi=13593&bbsId=8411",
            "https://www.goegn.kr/goegn/na/ntt/selectNttList.do?mi=13581&bbsId=8403",
            "https://www.goegn.kr/goegn/na/ntt/selectNttList.do?mi=13579&bbsId=8401",
        ]
        scoped = c.official_support_board_urls(src, stale)
        self.assertEqual(scoped, src["boardUrls"])
        self.assertEqual(len(scoped), 5)
        self.assertFalse(set(stale) & set(scoped))

    def test_live_cache_only_contains_authorized_board_urls(self):
        src = self.get_source()
        self.assertEqual(c.CACHE[GURI], src["boardUrls"])

    def test_mismatch_in_official_board_ids_fails_closed(self):
        src = dict(self.get_source())
        src["boardUrls"] = list(src["boardUrls"])
        src["boardUrls"][-1] = src["boardUrls"][-1].replace("bbsId=8656", "bbsId=8653")
        with self.assertRaisesRegex(ValueError, "registry drift"):
            c.official_support_board_urls(src, [])

    def test_other_office_caches_keep_existing_behavior(self):
        src = {"name": "다른교육지원청", "boardUrls": ["https://example.org/a"]}
        self.assertEqual(
            c.official_support_board_urls(src, ["https://example.org/b", "https://example.org/a"]),
            ["https://example.org/a", "https://example.org/b"],
        )

    def test_repeated_page_is_not_a_complete_coverage_proof(self):
        src = self.get_source()
        board = src["boardUrls"][0]
        page = (
            "<table><tr><th>제목</th><th>등록일</th></tr>"
            "<tr><td><a href=\"javascript:nttView('12345678')\">기간제교사 채용</a></td>"
            "<td>2026.11.10</td></tr></table>"
        )
        def fake_get(url, **kwargs):
            return SimpleNamespace(text=page, url=url)
        with patch.object(c, "get", side_effect=fake_get):
            with patch.object(c.time, "sleep", return_value=None):
                jobs, meta = c.gyeonggi_board(board, src)
        self.assertGreater(len(jobs), 0)
        self.assertTrue(meta["paginationRepeated"])
        self.assertFalse(meta["coverageComplete"])

    def test_all_five_boards_must_have_complete_metadata(self):
        src = self.get_source()
        boards = c.official_support_board_urls(src, [])
        metas = [
            {"url": board, "coverageComplete": True, "accessError": False,
             "paginationRepeated": False, "rawRows": 30, "pagesScanned": 3}
            for board in boards
        ]
        self.assertTrue(c.status_from_board(src["name"], src["url"], [], metas)["coverageComplete"])
        metas[3]["coverageComplete"] = False
        self.assertFalse(c.status_from_board(src["name"], src["url"], [], metas)["coverageComplete"])


if __name__ == "__main__":
    unittest.main()
