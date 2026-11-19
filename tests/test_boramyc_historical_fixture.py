#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from unittest.mock import Mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import crawl_boramyc_instructor_jobs as boramyc
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


class BoramaeHistoricalFixtureTest(unittest.TestCase):
    def test_25441_parser_and_direct_link_contract(self):
        fixture = (ROOT / "tests" / "fixtures" / "boramyc_25441.html").read_text(encoding="utf-8")
        url = boramyc.exact_url("25441")
        job = boramyc.detail(
            Session(Response(fixture, url)),
            {"idx": "25441", "title": "2026년 교육문화팀 생활체육(당구) 강사 채용 공고"},
        )
        self.assertEqual(job["sourceIdentity"], "boramyc:25441")
        self.assertEqual(job["registered"], "2026-08-26")
        self.assertEqual(job["applyEnd"], "2026-09-10")
        self.assertIn("당구", job["subject"])
        self.assertIn("체육", job["subject"])
        self.assertTrue(job["detailLinkVerified"])
        self.assertIn("idx=25441", job["url"])
        self.assertIn("ptype=view", job["url"])
        self.assertTrue(is_direct_post(job)[0], is_direct_post(job))


    def test_forbidden_source_does_not_retry_and_identifies_operator(self):
        response = boramyc.requests.Response()
        response.status_code = 403
        response.url = boramyc.LIST
        session = Mock()
        session.get.return_value = response
        with self.assertRaises(boramyc.requests.HTTPError):
            boramyc.get(session, boramyc.LIST)
        session.get.assert_called_once()
        self.assertIn("github.com/teacherhub-kr/gg-edujob", boramyc.HEADERS["User-Agent"])


if __name__ == "__main__":
    unittest.main()
