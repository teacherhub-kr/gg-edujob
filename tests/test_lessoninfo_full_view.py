import sys
import types
import unittest

try:
    import playwright.async_api  # noqa: F401
except ModuleNotFoundError:
    playwright = types.ModuleType("playwright")
    async_api = types.ModuleType("playwright.async_api")
    async_api.async_playwright = lambda: None
    async_api.TimeoutError = TimeoutError
    playwright.async_api = async_api
    sys.modules["playwright"] = playwright
    sys.modules["playwright.async_api"] = async_api

sys.path.insert(0, "scripts")
import crawl_lessoninfo_browser as lesson


class LessoninfoFullViewTests(unittest.TestCase):
    def test_status_labels_are_explicit(self):
        self.assertEqual(lesson.candidate_status("active"), ("current", "현재 공고"))
        self.assertEqual(
            lesson.candidate_status("stale-without-deadline"),
            ("deadline-unknown", "마감여부 미확인"),
        )
        self.assertEqual(
            lesson.candidate_status("detail-route-mismatch"),
            ("unverified-link", "상세링크 미검증"),
        )
        self.assertEqual(lesson.candidate_status("closed-marker"), ("closed", "마감"))

    def test_unverified_route_is_visible_but_not_clickable(self):
        item = {
            "sourceIdentity": "culture:id:123",
            "url": "https://www.lessoninfo.co.kr/culture-jobs/detail.php?id=123",
            "titleHint": "서울 문화예술 채용",
            "registeredHint": "2026-09-30",
            "sourceSurface": "culture-arts",
            "sourceSurfaceLabel": "문화예술 채용",
            "rowText": "서울 문화예술 채용",
        }
        row = lesson.project_candidate(item, "detail-route-mismatch", None, "2026-10-02T00:00:00+09:00")
        self.assertFalse(row["clickable"])
        self.assertEqual(row["url"], "")
        self.assertEqual(row["unverifiedDetailUrl"], item["url"])
        self.assertEqual(row["statusLabel"], "상세링크 미검증")

    def test_stale_without_deadline_retains_source_link(self):
        item = {
            "sourceIdentity": "board:test:1",
            "url": "https://www.lessoninfo.co.kr/board/board.php?wr_no=1",
            "titleHint": "경기 방과후 강사 구인",
            "registeredHint": "2026-08-01",
            "sourceSurface": "afterschool-nulbom",
            "sourceSurfaceLabel": "방과후교사•늘봄학교 강사",
            "rowText": "경기 방과후 강사 구인",
        }
        row = lesson.project_candidate(item, "stale-without-deadline", None, "2026-10-02T00:00:00+09:00")
        self.assertTrue(row["clickable"])
        self.assertEqual(row["statusLabel"], "마감여부 미확인")
        self.assertEqual(row["province"], "경기")

    def test_active_projection_uses_verified_current_row(self):
        item = {
            "sourceIdentity": "board:test:2",
            "url": "https://www.lessoninfo.co.kr/board/board.php?wr_no=2",
            "titleHint": "원래 제목",
            "registeredHint": "2026-10-01",
            "sourceSurface": "afterschool-nulbom",
            "sourceSurfaceLabel": "방과후교사•늘봄학교 강사",
            "rowText": "서울 중랑구",
        }
        active = {
            "sourceIdentity": "board:test:2",
            "title": "중랑구 초등학교 방과후 피아노 강사",
            "registered": "2026-10-01",
            "province": "서울",
            "metroRegion": "서울",
            "location": "서울 중랑구",
            "url": item["url"],
            "originalUrl": item["url"],
        }
        row = lesson.project_candidate(item, "active", active, "2026-10-02T00:00:00+09:00")
        self.assertTrue(row["isCurrent"])
        self.assertTrue(row["clickable"])
        self.assertEqual(row["statusGroup"], "current")
        self.assertEqual(row["title"], active["title"])


if __name__ == "__main__":
    unittest.main()
