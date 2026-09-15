#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import crawl_seekle_instructor_jobs as seekle
from direct_post_links import is_direct_post


class Response:
    status_code = 200

    def __init__(self, text: str, url: str):
        self.text = text
        self.url = url

    def raise_for_status(self):
        return None


class Session:
    def __init__(self, response: Response):
        self.response = response

    def get(self, url, **_kwargs):
        return self.response


class SeekleHistoricalFixtureTest(unittest.TestCase):
    def test_21827_parser_and_direct_link_contract(self):
        fixture = (ROOT / "tests" / "fixtures" / "seekle_21827.html").read_text(encoding="utf-8")
        title = "2026년 문화예술 강사 채용 공고 (2026. 9. 1. ~ 2026. 9. 18.)"
        url = seekle.exact_url("21827")
        job = seekle.detail(Session(Response(fixture, url)), {"idx": "21827", "title": title})
        self.assertEqual(job["sourceIdentity"], "seekle:21827")
        self.assertEqual(job["registered"], "2026-09-01")
        self.assertEqual(job["applyEnd"], "2026-09-18")
        self.assertIn("음악", job["subject"])
        self.assertIn("미술", job["subject"])
        self.assertTrue(job["detailLinkVerified"])
        self.assertIn("idx=21827", job["url"])
        self.assertIn("ptype=view", job["url"])
        self.assertTrue(is_direct_post(job)[0], is_direct_post(job))

    def test_empty_current_instructor_set_is_healthy(self):
        pages = {
            1: [{"idx": "30001", "title": "센터 운영 안내"}],
            2: [{"idx": "29999", "title": "시설 휴관 안내"}],
        }
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            previous = Path.cwd()
            try:
                os.chdir(temp_dir)
                with patch.object(seekle.requests, "Session", return_value=object()), patch.object(
                    seekle, "list_rows", side_effect=lambda _session, page: pages.get(page, [])
                ):
                    seekle.main()
                report = json.loads(Path("seekle_reconciliation_report.json").read_text(encoding="utf-8"))
                jobs = json.loads(Path("seekle_jobs.json").read_text(encoding="utf-8"))
            finally:
                os.chdir(previous)
        self.assertTrue(report["healthy"])
        self.assertEqual(report["jobCount"], 0)
        self.assertEqual(report["missingAfterCount"], 0)
        self.assertEqual(jobs, [])


if __name__ == "__main__":
    unittest.main()
