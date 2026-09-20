import unittest
from datetime import date
from pathlib import Path

from scripts import build_unified_search as unified


class PrivateMetroScopeTests(unittest.TestCase):
    def test_unified_accepts_incheon_private_posting(self):
        row = {
            "province": "인천",
            "title": "인천 연수구 음악강사 채용",
            "registered": date.today().isoformat(),
        }
        self.assertTrue(unified.private_current(row))
        self.assertEqual(
            unified.region_from({"province": "인천", "location": "인천 연수구"}),
            "연수구",
        )

    def test_jobteacher_has_verified_incheon_surface_code(self):
        text = Path("scripts/crawl_jobteacher_browser.py").read_text(encoding="utf-8")
        self.assertIn("'incheon': f'{BASE}/employ/lists/all/?is_search=yes&sel_area%5B%5D=907'", text)
        self.assertIn("'incheon':'인천'", text)

    def test_artmore_has_verified_incheon_surface_code(self):
        text = Path("scripts/crawl_artmore_browser.py").read_text(encoding="utf-8")
        self.assertIn('("인천", "2053")', text)
        self.assertIn('"인천": re.compile', text)

    def test_multi_region_private_collectors_and_validators_include_incheon(self):
        gonggong = Path("scripts/crawl_gonggonggangsa_jobs.py").read_text(encoding="utf-8")
        validator = Path("scripts/validate_unified_search_multi.py").read_text(encoding="utf-8")
        crosscheck = Path("scripts/crosscheck_private_official.py").read_text(encoding="utf-8")
        self.assertIn('{"서울", "경기", "인천"}', gonggong)
        self.assertIn('{"서울", "경기", "인천"}', validator)
        self.assertIn('{"서울","경기","인천"}', crosscheck)
        self.assertIn("'인천':[]", crosscheck)

    def test_lessoninfo_treats_incheon_as_metro(self):
        fast = Path("scripts/run_lessoninfo_browser_fast.py").read_text(encoding="utf-8")
        resilient = Path("scripts/run_lessoninfo_browser_resilient.py").read_text(encoding="utf-8")
        self.assertIn("INCHEON_DISTRICTS", fast)
        self.assertIn('return "인천"', fast)
        self.assertIn('{"서울", "경기", "인천"}', resilient)


if __name__ == "__main__":
    unittest.main()
