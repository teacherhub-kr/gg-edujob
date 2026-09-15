#!/usr/bin/env python3
from __future__ import annotations

import io
import hashlib
import sys
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from support_page_evidence import official_page_evidence


FIXTURES = ROOT / "tests" / "fixtures" / "support_evidence"
AS_OF = date(2026, 9, 15)


def fixture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def no_attachment(_url, _referer):
    raise AssertionError("fixture must not load an attachment")


class SupportPageEvidenceTest(unittest.TestCase):
    def test_mircms_page_application_deadline(self):
        evidence = official_page_evidence(
            fixture("mircms_detail.html"),
            "mircms:www.example.kr:1234:5678",
            "https://www.example.kr/notice?bbsId=1234&nttSn=5678",
            as_of=AS_OF,
            attachment_loader=no_attachment,
        )
        self.assertEqual(evidence["kind"], "deadline")
        self.assertEqual(evidence["date"], "2026-06-16")
        self.assertEqual(evidence["evidence"], "mircms-page:application-deadline")

    def test_mircms_hwpx_attachment_deadline(self):
        payload = io.BytesIO()
        with zipfile.ZipFile(payload, "w") as document:
            document.writestr(
                "Contents/section0.xml",
                "<section><p>서류접수 기간: 2026. 6. 11. ~ 6. 17. 15:00까지</p></section>",
            )
        evidence = official_page_evidence(
            fixture("mircms_attachment_detail.html"),
            "mircms:www.example.kr:1234:5678",
            "https://www.example.kr/notice?bbsId=1234&nttSn=5678",
            as_of=AS_OF,
            attachment_loader=lambda _url, _referer: payload.getvalue(),
        )
        self.assertEqual(evidence["kind"], "deadline")
        self.assertEqual(evidence["date"], "2026-06-17")
        self.assertIn("mircms-attachment", evidence["evidence"])

    def test_direct_receipt_method_is_not_mistaken_for_future_deadline(self):
        evidence = official_page_evidence(
            fixture("mircms_direct_receipt.html"),
            "mircms:www.example.kr:1234:5678",
            "https://www.example.kr/notice?bbsId=1234&nttSn=5678",
            as_of=AS_OF,
            attachment_loader=no_attachment,
        )
        self.assertEqual(evidence["kind"], "ended")
        self.assertEqual(evidence["date"], "2026-08-18")
        self.assertIn("activity-period-started", evidence["evidence"])

    def test_numbered_application_period_label(self):
        html = fixture("mircms_detail.html").replace(
            "접수 기간: 2026. 6. 11. ~ 6. 16. 12:00",
            "원서 접수 가. 기간: 2026. 6. 11. ~ 6. 16. 12:00",
        )
        evidence = official_page_evidence(
            html,
            "mircms:www.example.kr:1234:5678",
            "https://www.example.kr/notice?bbsId=1234&nttSn=5678",
            as_of=AS_OF,
            attachment_loader=no_attachment,
        )
        self.assertEqual(evidence["date"], "2026-06-16")

    def test_closed_period_precedes_indefinite_contingency(self):
        html = fixture("mircms_detail.html").replace(
            "접수 기간: 2026. 6. 11. ~ 6. 16. 12:00",
            "접수 기간: 2026. 6. 11. ~ 6. 16. 12:00. 단, 미충원 시까지",
        )
        evidence = official_page_evidence(
            html,
            "mircms:www.example.kr:1234:5678",
            "https://www.example.kr/notice?bbsId=1234&nttSn=5678",
            as_of=AS_OF,
            attachment_loader=no_attachment,
        )
        self.assertEqual(evidence["date"], "2026-06-16")

    def test_reviewed_binary_evidence_is_hash_pinned_and_fail_closed(self):
        payload = b"reviewed official image fixture"
        artifact_url = "https://www.example.kr/evidence.jpg"
        records = {
            "mircms:www.example.kr:1234:5678": {
                "artifactUrl": artifact_url,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "kind": "deadline",
                "date": "2026-06-17",
                "basis": "application-deadline",
            }
        }
        html = '<form id="nttViewForm"><div class="bbsV_cont"><img src="/evidence.jpg"></div></form>'
        with patch("support_page_evidence.REVIEWED_BINARY_EVIDENCE", records):
            evidence = official_page_evidence(
                html,
                "mircms:www.example.kr:1234:5678",
                "https://www.example.kr/detail",
                as_of=AS_OF,
                attachment_loader=lambda _url, _referer: payload,
            )
            self.assertEqual(evidence["date"], "2026-06-17")
            self.assertIsNone(official_page_evidence(
                html,
                "mircms:www.example.kr:1234:5678",
                "https://www.example.kr/detail",
                as_of=AS_OF,
                attachment_loader=lambda _url, _referer: b"changed",
            ))

    def test_seoul_structured_deadline(self):
        evidence = official_page_evidence(
            fixture("seoul_jov_detail.html"),
            "seoul:jbedu.sen.go.kr:3385",
            "https://jbedu.sen.go.kr/FUS/JO/JOV11.do?job_seq=3385",
            as_of=AS_OF,
            attachment_loader=no_attachment,
        )
        self.assertEqual(evidence, {"kind": "deadline", "evidence": "seoul-jov:deadline-field", "date": "2026-06-15"})

    def test_seoul_past_selection_event_is_explicit_end_evidence(self):
        evidence = official_page_evidence(
            fixture("seoul_jov_selection.html"),
            "seoul:gsycedu.sen.go.kr:14949",
            "https://gsycedu.sen.go.kr/FUS/JO/JOV11.do?job_seq=14949",
            as_of=AS_OF,
            attachment_loader=no_attachment,
        )
        self.assertEqual(evidence["kind"], "ended")
        self.assertEqual(evidence["evidence"], "seoul-jov:selection-event-ended")

    def test_wrong_source_family_or_detail_id_has_no_evidence(self):
        html = fixture("seoul_jov_detail.html")
        self.assertIsNone(official_page_evidence(html, "seoul:jbedu.sen.go.kr:9999", "https://example", as_of=AS_OF, attachment_loader=no_attachment))
        self.assertIsNone(official_page_evidence(html, "", "https://example", as_of=AS_OF, attachment_loader=no_attachment))


if __name__ == "__main__":
    unittest.main()
