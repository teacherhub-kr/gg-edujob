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
import build_unified_search_multi as multi
from private_source_registry import lessoninfo_full_candidate_publishable, merge_lessoninfo_full_candidates


class LessoninfoFullViewTests(unittest.TestCase):
    def test_unified_publishable_never_reintroduces_explicitly_closed_posts(self):
        from datetime import datetime, timedelta
        from build_unified_search import KST
        today = datetime.now(KST).date()
        self.assertTrue(lessoninfo_full_candidate_publishable({"statusGroup": "current"}))
        self.assertTrue(lessoninfo_full_candidate_publishable({"statusGroup": "deadline-unknown", "registered": today.isoformat()}))
        self.assertFalse(lessoninfo_full_candidate_publishable({"statusGroup": "deadline-unknown", "registered": (today - timedelta(days=15)).isoformat()}))
        self.assertTrue(lessoninfo_full_candidate_publishable({"statusGroup": "unverified-link"}))
        self.assertFalse(lessoninfo_full_candidate_publishable({"statusGroup": "closed"}))
        self.assertFalse(lessoninfo_full_candidate_publishable({"statusGroup": "current", "statusLabel": "마감"}))
        self.assertFalse(lessoninfo_full_candidate_publishable({"statusGroup": "current", "applyEnd": (today - timedelta(days=1)).isoformat()}))
        self.assertTrue(lessoninfo_full_candidate_publishable({"statusGroup": "current", "applyEnd": today.isoformat()}))
        self.assertFalse(lessoninfo_full_candidate_publishable({"statusGroup": "out-of-scope"}))
        self.assertTrue(lessoninfo_full_candidate_publishable({"statusGroup": "out-of-scope", "province": "인천"}))
        self.assertFalse(lessoninfo_full_candidate_publishable({"statusGroup": "excluded"}))

    def test_full_candidate_merge_preserves_status_and_active_link_evidence(self):
        full = [{
            "sourceIdentity": "culture:id:777",
            "statusGroup": "current",
            "statusLabel": "현재 공고",
            "classificationReason": "active",
            "isCurrent": True,
            "clickable": True,
            "url": "",
        }]
        active = [{
            "sourceIdentity": "culture:id:777",
            "url": "https://example.org/official/777",
            "originalUrl": "https://example.org/official/777",
            "verifiedUrl": "https://example.org/official/777",
            "detailLinkVerified": True,
            "linkedOfficialUrls": ["https://example.org/official/777"],
        }]
        row = merge_lessoninfo_full_candidates(full, active)[0]
        self.assertEqual(row["statusGroup"], "current")
        self.assertTrue(row["isCurrent"])
        self.assertEqual(row["verifiedUrl"], "https://example.org/official/777")
        self.assertEqual(row["linkedOfficialUrls"], ["https://example.org/official/777"])

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


    def test_audit_breakdown_distinguishes_source_current_unknown_and_unsafe_links(self):
        original = [
            {"sourceIdentity": "board:1", "statusGroup": "current", "title": "음악교사 모집"},
            {"sourceIdentity": "board:2", "statusGroup": "deadline-unknown", "title": "마감일 미상"},
            {"sourceIdentity": "board:3", "statusGroup": "unverified-link", "title": "상세 링크 미확인"},
            {"sourceIdentity": "board:4", "statusGroup": "closed", "title": "모집 종료"},
        ]
        selected = [original[0], original[2]]
        projected = [
            {"url": "https://school.example/jobs/1", "detailLinkVerified": True},
            {"url": "", "detailLinkVerified": False},
        ]
        snapshot = [dict(row) for row in original]
        report = multi.summarize_lessoninfo_evidence(original, selected, projected, True)
        self.assertEqual(report["rawCandidates"], 4)
        self.assertEqual(report["selectedCandidates"], 2)
        self.assertEqual(report["excludedCandidates"], 2)
        self.assertEqual(report["sourceStatusCounts"]["deadline-unknown"], 1)
        self.assertEqual(report["unknownDeadlineExcluded"], 1)
        self.assertEqual(report["unverifiedLinkSelected"], 1)
        self.assertEqual(report["selectedWithVerifiedDirectUrl"], 1)
        self.assertEqual(report["selectedWithoutVerifiedDirectUrl"], 1)
        self.assertEqual(report["sourceLabeledCurrentSelected"], 1)
        self.assertEqual(original, snapshot, "An audit must not mutate the canonical candidate rows")

    def test_evidence_reporting_never_claims_disabled_source_is_published(self):
        rows = [{"statusGroup": "current", "sourceIdentity": "board:1"}]
        projected = [{"url": "", "detailLinkVerified": False}]
        report = multi.summarize_lessoninfo_evidence(rows, rows, projected, False)
        self.assertEqual(report["selectedCandidates"], 1)
        self.assertEqual(report["publishedSourceOccurrencesBeforeDedup"], 0)
        self.assertEqual(report["selectedWithVerifiedDirectUrl"], 0)
        self.assertFalse(report["publicationEnabled"])



if __name__ == "__main__":
    unittest.main()
