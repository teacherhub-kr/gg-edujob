#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from stable_source_identity import canonical_source_id, seoul_cms_detail_id


class StableSourceIdentityTest(unittest.TestCase):
    def seoul(self, url, **extra):
        return canonical_source_id({"province": "서울", "url": url, **extra})

    def test_static_cms_ignores_scheme_fragment_and_meaningless_query(self):
        path = "/CMS/openedu/openedu02/openedu0201/1358918_3667.html"
        expected = "seoul-cms:gnscedu.sen.go.kr:3667:1358918"
        self.assertEqual(self.seoul("http://GNSCEDU.SEN.GO.KR" + path), expected)
        self.assertEqual(self.seoul("https://gnscedu.sen.go.kr" + path + "?page=3#content"), expected)

    def test_static_cms_article_host_and_board_are_identity_components(self):
        base = "/CMS/openedu/openedu02/openedu0201/"
        first = self.seoul("https://a.sen.go.kr" + base + "1358918_3667.html")
        self.assertNotEqual(first, self.seoul("https://a.sen.go.kr" + base + "1358919_3667.html"))
        self.assertNotEqual(first, self.seoul("https://b.sen.go.kr" + base + "1358918_3667.html"))
        self.assertNotEqual(first, self.seoul("https://a.sen.go.kr" + base + "1358918_3668.html"))

    def test_existing_job_seq_identity_is_unchanged(self):
        job = {
            "province": "서울",
            "url": "https://sbedu.sen.go.kr/FUS/JO/JOV11.do?noise=1",
            "openUrl": "HTTPS://SBEDU.SEN.GO.KR/FUS/JO/JOV11.do",
            "openParams": {"job_seq": "5592"},
        }
        self.assertEqual(canonical_source_id(job), "seoul:sbedu.sen.go.kr:5592")

    def test_gyeonggi_bbs_and_ntt_identity_is_unchanged(self):
        job = {
            "province": "경기",
            "url": "https://goesn.kr/board/view.do?bbsId=1234&nttSn=567890",
        }
        self.assertEqual(canonical_source_id(job), "mircms:goesn.kr:1234:567890")

    def test_central_identities_are_unchanged(self):
        gyeonggi = {
            "sourceType": "통합게시판",
            "province": "경기",
            "url": "https://www.goe.go.kr/view.do?pbancSn=98765",
        }
        seoul = {
            "sourceType": "통합게시판",
            "province": "서울",
            "url": "https://work.sen.go.kr/view.do?q_rcrtSn=32078",
        }
        self.assertEqual(canonical_source_id(gyeonggi), "goe-central:98765")
        self.assertEqual(canonical_source_id(seoul), "seoul-central:32078")

    def test_list_home_search_and_malformed_urls_have_no_strong_id(self):
        rejected = (
            "https://gnscedu.sen.go.kr/",
            "https://gnscedu.sen.go.kr/CMS/openedu/openedu02/openedu0201/index.html",
            "https://gnscedu.sen.go.kr/CMS/search/search.do?q=1358918_3667.html",
            "https://gnscedu.sen.go.kr/CMS/search/results/1358918_3667.html",
            "https://gnscedu.sen.go.kr/CMS/openedu/1358918_3667.htm",
            "https://gnscedu.sen.go.kr/CMS/openedu/not-an-id_3667.html",
            "https://sbedu.sen.go.kr/FUS/JO/JOL11.do?job_seq=5592",
            "not a url/CMS/openedu/1358918_3667.html",
            "javascript:1358918_3667.html",
        )
        for url in rejected:
            with self.subTest(url=url):
                self.assertEqual(self.seoul(url), "")
                self.assertEqual(seoul_cms_detail_id(url), "")

    def test_known_parse_failure_fixtures_are_resolved(self):
        fixtures = [
            line.strip()
            for line in (ROOT / "tests" / "fixtures" / "seoul_cms_parse_failures.txt")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip() and not line.startswith("#")
        ]
        self.assertEqual(len(fixtures), 1)
        resolved = [self.seoul(url) for url in fixtures]
        self.assertEqual(resolved, ["seoul-cms:gnscedu.sen.go.kr:3667:1358918"])

    def test_reconciliation_audit_and_dedup_consumers_share_the_parser(self):
        import audit_operational_quality
        import build_unified_search
        import merge_recovery_snapshot
        import reconcile_source_ids
        import update_collection_state
        import update_collector_status

        job = {
            "province": "서울",
            "url": "https://gnscedu.sen.go.kr/CMS/openedu/openedu02/openedu0201/1358918_3667.html",
        }
        expected = "seoul-cms:gnscedu.sen.go.kr:3667:1358918"
        consumers = (
            audit_operational_quality.stable_id,
            build_unified_search.official_stable_id,
            merge_recovery_snapshot.stable_source_id,
            reconcile_source_ids.source_id,
            update_collection_state.identity,
            update_collector_status.stable_source_id,
        )
        for consumer in consumers:
            with self.subTest(consumer=consumer.__module__):
                self.assertEqual(consumer(job), expected)


if __name__ == "__main__":
    unittest.main()
