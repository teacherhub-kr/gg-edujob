#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import audit_support_71_diff as audit
from stable_source_identity import canonical_source_id

AS_OF = date(2026, 9, 15)


def seoul(seq, *, title="공고", url_host="sbedu.sen.go.kr", end="2026-09-30"):
    return {"province": "서울", "source": "강서양천교육지원청", "title": title, "applyEnd": end, "url": f"https://{url_host}/FUS/JO/JOV11.do?job_seq={seq}"}


def gyeonggi(ntt, *, title="공고", end="2026-09-30"):
    return {"province": "경기", "source": "수원교육지원청", "title": title, "applyEnd": end, "url": f"https://www.goesw.kr/board/view.do?bbsId=1234&nttSn={ntt}"}


def mircms(ntt, *, end=""):
    return {"province": "경기", "source": "수원교육지원청", "title": "공고", "applyEnd": end, "url": f"https://www.goesw.kr/na/ntt/selectNttInfo.do?bbsId=1234&nttSn={ntt}"}


def ok(url="https://official.example/detail"):
    return {"status": "ok", "http": 200, "finalUrl": url, "body": "채용 공고 상세"}


class SupportDiffAuditTest(unittest.TestCase):
    def test_reference_counts_do_not_control_health(self):
        jobs = [seoul("101"), gyeonggi("201")]
        report = audit.audit_report(jobs, list(jobs), as_of=AS_OF, probe=lambda _: ok())
        self.assertTrue(report["healthy"])
        self.assertFalse(report["historicalReferenceMatches"])

    def test_same_strong_id_url_move_is_normal(self):
        old = seoul("101", url_host="SBEDU.SEN.GO.KR")
        current = seoul("101", url_host="sbedu.sen.go.kr")
        result = audit.classify(old, {audit.identity(current): current}, as_of=AS_OF)
        self.assertEqual(result["classification"], audit.STRONG_ID_MOVE)

    def test_same_title_is_not_identity(self):
        old = seoul("101", title="같은 제목")
        current = seoul("102", title="같은 제목")
        result = audit.classify(old, {audit.identity(current): current}, as_of=AS_OF, probe=lambda _: ok(old["url"]))
        self.assertEqual(result["classification"], audit.ACTUAL_MISSING)
        self.assertNotIn("newId", result)

    def test_active_reachable_missing_is_reported(self):
        old = seoul("101")
        report = audit.audit_report([old], [], as_of=AS_OF, probe=lambda _: ok(old["url"]))
        self.assertFalse(report["healthy"])
        self.assertEqual(len(report["actualMissing"]), 1)
        self.assertEqual(report["actualMissing"][0]["oldId"], "seoul:sbedu.sen.go.kr:101")

    def test_unverifiable_is_fail_closed(self):
        old = seoul("101", end="")
        report = audit.audit_report([old], [], as_of=AS_OF, probe=lambda _: ok(old["url"]))
        self.assertFalse(report["healthy"])
        self.assertEqual(len(report["unverifiable"]), 1)

    def test_official_page_deadline_replaces_missing_apply_end(self):
        old = mircms("201")
        expired_html = '<form id="nttViewForm"><div class="bbsV_cont">원서 접수 가. 기간: 2026. 6. 11. ~ 6. 17.</div></form>'
        active_html = '<form id="nttViewForm"><div class="bbsV_cont">원서 접수 가. 기간: 2026. 9. 15. ~ 9. 30.</div></form>'
        no_attachment = lambda *_: (_ for _ in ()).throw(AssertionError("no attachment expected"))
        expired = audit.classify(old, {}, as_of=AS_OF, probe=lambda _: {**ok(old["url"]), "body": expired_html}, attachment_loader=no_attachment)
        active = audit.classify(old, {}, as_of=AS_OF, probe=lambda _: {**ok(old["url"]), "body": active_html}, attachment_loader=no_attachment)
        self.assertEqual(expired["classification"], audit.EXPIRED)
        self.assertEqual(active["classification"], audit.ACTUAL_MISSING)

    def test_parse_failure_and_collision_are_fail_closed(self):
        malformed = {"province": "서울", "source": "강서양천교육지원청", "title": "목록", "url": "https://sbedu.sen.go.kr/search"}
        duplicate = seoul("101")
        report = audit.audit_report([duplicate, dict(duplicate)], [malformed], as_of=AS_OF, probe=lambda _: ok())
        self.assertFalse(report["healthy"])
        self.assertEqual(report["normalizedCollisionCount"]["historical"], 1)
        self.assertEqual(report["identityParseFailureCount"]["current"], 1)

    def test_seoul_cms_identity_is_used(self):
        job = {"province": "서울", "source": "강남서초교육지원청", "title": "CMS 공고", "url": "https://gnscedu.sen.go.kr/CMS/openedu/openedu02/openedu0201/1358918_3667.html"}
        self.assertEqual(audit.identity(job), "seoul-cms:gnscedu.sen.go.kr:3667:1358918")

    def test_existing_identity_families_remain_supported(self):
        cases = (
            (gyeonggi("567890"), "mircms:www.goesw.kr:1234:567890"),
            (seoul("5592"), "seoul:sbedu.sen.go.kr:5592"),
            ({"province": "경기", "sourceType": "통합게시판", "url": "https://goe.go.kr/view?pbancSn=98765"}, "goe-central:98765"),
            ({"province": "서울", "sourceType": "통합게시판", "url": "https://work.sen.go.kr/view?q_rcrtSn=32078"}, "seoul-central:32078"),
        )
        for job, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(canonical_source_id(job), expected)

    def test_official_end_expiry_and_canonical_redirect_are_distinct(self):
        expired = audit.classify(seoul("101", end="2026-09-14"), {}, as_of=AS_OF)
        deleted = audit.classify(seoul("102"), {}, as_of=AS_OF, probe=lambda _: {"status": "ok", "http": 404, "finalUrl": "", "body": ""})
        moved = seoul("103", url_host="new.sen.go.kr")
        redirected = audit.classify(seoul("102"), {audit.identity(moved): moved}, as_of=AS_OF, probe=lambda _: ok(moved["url"]))
        self.assertEqual(expired["classification"], audit.EXPIRED)
        self.assertEqual(deleted["classification"], audit.OFFICIAL_ENDED)
        self.assertEqual(redirected["classification"], audit.CANONICAL_URL_MOVE)


if __name__ == "__main__":
    unittest.main()
