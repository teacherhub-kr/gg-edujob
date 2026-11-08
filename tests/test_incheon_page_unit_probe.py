import json
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import merge_incheon_official as ice  # noqa: E402
import probe_incheon_page_unit as probe  # noqa: E402

TODAY = date(2026, 11, 8)


def board_html(ids_dates, total=None):
    rows = "".join(
        f'<tr><td>{i}</td><td><a class="nttInfoBtn" data-id="{ntt}" href="#">공고 {ntt}</a></td>'
        f"<td>{d}</td></tr>"
        for i, (ntt, d) in enumerate(ids_dates)
    )
    total_text = f"<p>총 {total}건</p>" if total else ""
    return (
        "<html><body>" + total_text +
        '<form name="pagingForm" action="/ice/na/ntt/selectNttList.do" method="post">'
        '<input name="bbsId" value="1981"><input name="mi" value="10997">'
        '<input name="currPage" value="1"><input name="CSRFToken" value="SECRET-TOKEN"></form>'
        "<table><tr><th>번호</th><th>제목</th><th>등록일</th></tr>" + rows + "</table></body></html>"
    )


def posts(count, start=TODAY):
    # Two posts per day, newest first.
    return [(str(5000000 - n), (start - timedelta(days=n // 2)).isoformat()) for n in range(count)]


class FakeResponse:
    def __init__(self, url, html):
        self.url = url
        self.text = html
        self.status_code = 200


class FakeSession:
    """Default page = 10 rows; only `honored` page-size parameter returns more rows."""

    def __init__(self, honored, method="GET", window=200):
        self.honored = honored
        self.honored_method = method
        self.all = posts(window)
        self.posted_bodies = []

    def _page(self, params, method):
        size = 10
        value = params.get(self.honored)
        if value and method == self.honored_method:
            size = int(value)
        return board_html(self.all[:size])

    def get(self, url, **_kwargs):
        params = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
        return FakeResponse(url, self._page(params, "GET"))

    def post(self, url, data=None, **_kwargs):
        self.posted_bodies.append(list(data or []))
        return FakeResponse(url, self._page(dict(data or []), "POST"))

    def close(self):
        pass


def run_probe(session):
    with mock.patch.object(ice, "reset_session", lambda: None), mock.patch.object(ice, "SESSION", session):
        return probe.probe_board(ice.REQUIRED_BOARDS[0], 300, 14, TODAY)


class IncheonPageUnitProbeTests(unittest.TestCase):
    def test_honored_get_page_size_is_a_closed_coverage_candidate(self):
        result = run_probe(FakeSession("pageUnit", "GET"))
        self.assertEqual(result["coverageCandidates"], ["GET pageUnit=300"])
        winner = next(v for v in result["variants"] if v["label"] == "GET pageUnit=300")
        self.assertTrue(winner["closedByDate"])
        self.assertEqual(winner["rows"], 200)

    def test_honored_post_page_size_is_detected(self):
        result = run_probe(FakeSession("recordCountPerPage", "POST"))
        self.assertEqual(result["coverageCandidates"], ["POST pagingForm recordCountPerPage=300"])

    def test_ignored_page_size_is_never_a_candidate(self):
        result = run_probe(FakeSession("nothing-is-honored"))
        self.assertEqual(result["coverageCandidates"], [])
        self.assertTrue(all("page-size-not-honored" in v["rejectReasons"] for v in result["variants"]))

    def test_open_window_is_rejected_even_when_more_rows_return(self):
        baseline = {"ids": [str(n) for n in range(10)], "rows": 10, "displayedTotal": None}
        variant = {"status": 200, "rows": 20, "uniqueIds": 20, "ids": [str(n) for n in range(20)],
                   "datesNonIncreasing": True, "oldest": TODAY.isoformat(), "displayedTotal": None}
        verdict = probe.judge(baseline, variant, 14, TODAY)
        self.assertFalse(verdict["coverageCandidate"])
        self.assertIn("window-not-closed", verdict["rejectReasons"])

    def test_different_head_is_rejected(self):
        baseline = {"ids": ["1", "2"], "rows": 2, "displayedTotal": 3}
        variant = {"status": 200, "rows": 3, "uniqueIds": 3, "ids": ["9", "1", "2"],
                   "datesNonIncreasing": True, "oldest": "2026-01-01", "displayedTotal": 3}
        self.assertIn("default-page-not-head", probe.judge(baseline, variant, 14, TODAY)["rejectReasons"])

    def test_report_never_contains_form_values_or_tokens(self):
        session = FakeSession("pageUnit", "GET")
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(ice, "reset_session", lambda: None), \
                mock.patch.object(ice, "SESSION", session), \
                mock.patch.object(ice, "REQUIRED_BOARDS", ice.REQUIRED_BOARDS[:1]):
            report = Path(tmp) / "r.json"
            self.assertEqual(probe.main(["--report", str(report)]), 0)
            text = report.read_text(encoding="utf-8")
        self.assertNotIn("SECRET-TOKEN", text)
        self.assertIn("CSRFToken", json.loads(text)["boards"][0]["pagingFormFieldNames"])
        # The token is replayed only inside the request body, never stored.
        self.assertTrue(any(("CSRFToken", "SECRET-TOKEN") in body for body in session.posted_bodies))

    def test_probe_never_touches_production_files(self):
        source = (ROOT / "scripts/probe_incheon_page_unit.py").read_text(encoding="utf-8")
        for forbidden in ("JOBS_PATH", "REPORT_PATH", "merge_into_jobs", "write_report", "jobs.json\""):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
