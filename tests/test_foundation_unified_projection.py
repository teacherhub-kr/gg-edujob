import sys
import unittest
from datetime import timedelta

sys.path.insert(0, "scripts")
import build_unified_search_multi as unified
import reconcile_cultural_foundation_coverage as coverage


class FoundationOfficialProjectionTests(unittest.TestCase):
    def post(self, **changes):
        today = unified.base.TODAY
        row = {
            "foundationRegistryId": "incheon:metropolitan",
            "foundationName": "인천문화재단",
            "sourceIdentity": "official-foundation:incheon:metropolitan:236088",
            "sourceRole": "primary-official",
            "province": "인천",
            "detailLinkVerified": True,
            "transportVerified": True,
            "title": "재단법인 인천문화재단 감사(비상임) 모집 공고",
            "registered": (today - timedelta(days=2)).isoformat(),
            "applyEnd": (today + timedelta(days=8)).isoformat(),
            "url": "https://ifac.or.kr/bbs/view.do?bbsSn=236088&key=m2501152808232",
        }
        row.update(changes)
        return row

    def test_verified_incheon_official_post_enters_official_feed(self):
        row = self.post()
        self.assertTrue(unified.foundation_official_current(row))
        projected = unified.project_foundation_official(row)
        self.assertEqual(projected["feedKind"], "official")
        self.assertEqual(projected["foundationRegistryId"], "incheon:metropolitan")
        self.assertNotEqual(
            unified.base.canonical_url(self.post()["url"]),
            unified.base.canonical_url(self.post(url="https://ifac.or.kr/bbs/view.do?bbsSn=236087&key=m2501152808232")["url"]),
        )

    def test_municipal_board_other_employers_do_not_become_foundation_jobs(self):
        other = self.post(
            foundationRegistryId="incheon:seohae", foundationName="인천서해구문화재단",
            title="서해구 보건소장 채용 공고",
        )
        own = self.post(
            foundationRegistryId="incheon:seohae", foundationName="인천서해구문화재단",
            title="2026년 인천서해구문화재단 직원 채용 공고",
        )
        self.assertFalse(unified.foundation_official_current(other))
        self.assertTrue(unified.foundation_official_current(own))

    def test_expired_unverified_or_insecure_posts_are_excluded(self):
        today = unified.base.TODAY
        self.assertFalse(unified.foundation_official_current(self.post(applyEnd="")))
        self.assertFalse(unified.foundation_official_current(self.post(applyEnd=(today-timedelta(days=1)).isoformat())))
        self.assertFalse(unified.foundation_official_current(self.post(detailLinkVerified=False)))
        self.assertFalse(unified.foundation_official_current(self.post(url="http://ifac.or.kr/bbs/view.do?bbsSn=236088")))

    def test_unverified_deadline_window_matches_coverage_reconciliation(self):
        today = unified.base.TODAY
        boundary = self.post(
            foundationRegistryId="seoul:guro",
            foundationName="구로문화재단",
            title="구로문화재단 정규직 공개경쟁채용 모집공고",
            applyEnd="",
            deadlineVerification="unverified-recent-official-post",
            registered=(today - timedelta(days=14)).isoformat(),
            url="https://www.guro.go.kr/www/selectBbsNttView.do?bbsNo=664&nttNo=240430&key=1792",
        )
        stale = dict(boundary, registered=(today - timedelta(days=15)).isoformat())
        self.assertTrue(unified.foundation_official_current(boundary))
        self.assertTrue(coverage.current(boundary, today))
        self.assertFalse(unified.foundation_official_current(stale))
        self.assertFalse(coverage.current(stale, today))

    def test_coverage_rejects_primary_official_without_deadline_evidence(self):
        today = unified.base.TODAY
        row = self.post(applyEnd="", registered=(today - timedelta(days=2)).isoformat())
        self.assertFalse(unified.foundation_official_current(row))
        self.assertFalse(coverage.current(row, today))


if __name__ == "__main__":
    unittest.main()
