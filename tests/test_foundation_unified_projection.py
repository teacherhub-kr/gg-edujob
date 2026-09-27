import sys
import unittest
from datetime import timedelta

sys.path.insert(0, "scripts")
import build_unified_search_multi as unified


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


if __name__ == "__main__":
    unittest.main()
