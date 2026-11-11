"""Fake-clock contract tests for ICE's ~11-second same-session page replay."""

import inspect
import unittest
from datetime import timedelta
from unittest import mock

from scripts import merge_incheon_official as ice

REPLAY_WINDOW_SECONDS = 11.0
BOARD = ice.REQUIRED_BOARDS[0]


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += max(0.0, float(seconds))


def list_page(page, total_pages, rows_per_page=10):
    newest = ice.NOW.date()
    rows = []
    if page <= total_pages:
        for index in range(rows_per_page):
            serial = 5_000_000 - (page - 1) * rows_per_page - index
            age = 1 if page < total_pages else 30
            registered = (newest - timedelta(days=age)).strftime("%Y/%m/%d")
            rows.append(
                f'<tr><td>모집중</td><td>테스트학교</td><td>시간강사</td>'
                f'<td><a class="nttInfoBtn" data-id="{serial}" href="#">공고 {serial}</a></td>'
                f"<td>{registered}</td></tr>"
            )
    return (
        "<html><body>"
        '<form name="pagingForm" method="post" action="/ice/na/ntt/selectNttList.do">'
        f'<input type="hidden" name="currPage" value="{page}">'
        '<input type="hidden" name="bbsId" value="1981">'
        '<input type="hidden" name="mi" value="10997">'
        '<input type="hidden" name="CSRFToken" value="123e4567-e89b-12d3-a456-426614174000">'
        "</form><table><tr><th>모집상태</th><th>기관명</th>"
        "<th>모집직종</th><th>제목</th><th>등록일</th></tr>"
        + "".join(rows)
        + "</table>" + "x" * 400 + "</body></html>"
    )


class Response:
    def __init__(self, text):
        self.text = text
        self.url = ice.LIST_URL
        self.content = text.encode("utf-8")
        self.encoding = "utf-8"
        self.apparent_encoding = "utf-8"
        self.status_code = 200
        self.headers = {"content-type": "text/html"}
        self.cookies = []
        self.history = []

    def raise_for_status(self):
        return None


class ReplayingIceSession:
    """For the first 11 seconds, serve the previous honored page."""

    def __init__(self, clock, total_pages):
        self.clock = clock
        self.total_pages = total_pages
        self.last_honored_at = None
        self.last_body = None
        self.requested = []

    def _serve(self, page):
        self.requested.append((round(self.clock.now, 2), page))
        if (
            self.last_honored_at is not None
            and self.clock.now - self.last_honored_at < REPLAY_WINDOW_SECONDS
        ):
            return Response(self.last_body)
        self.last_honored_at = self.clock.now
        self.last_body = list_page(page, self.total_pages)
        return Response(self.last_body)

    def get(self, url, **_kwargs):
        query = dict(
            part.split("=", 1) for part in url.split("?", 1)[1].split("&")
        ) if "?" in url else {}
        return self._serve(int(query.get("currPage", 1)))

    def post(self, _url, data=None, **_kwargs):
        return self._serve(int(dict(data or []).get("currPage", 1)))

    def close(self):
        pass


def run_board(interval, total_pages=4):
    clock = FakeClock()
    session = ReplayingIceSession(clock, total_pages)
    with mock.patch.object(ice, "SESSION", session), \
            mock.patch.object(ice, "reset_session", lambda: None), \
            mock.patch.object(ice, "MIN_REQUEST_INTERVAL_SECONDS", interval), \
            mock.patch.object(ice, "_LAST_ICE_REQUEST_AT", None), \
            mock.patch.object(ice.time, "monotonic", clock.monotonic), \
            mock.patch.object(ice.time, "sleep", clock.sleep):
        rows, meta = ice.scrape_board(
            BOARD, lookback_days=14, max_pages=20, check_only=False
        )
    return rows, meta, session


class IcePacingContractTests(unittest.TestCase):
    def test_default_interval_clears_measured_replay_window(self):
        self.assertGreater(ice.DEFAULT_MIN_REQUEST_INTERVAL_SECONDS, REPLAY_WINDOW_SECONDS)

    def test_unpaced_collector_reproduces_repeated_page_failure(self):
        _rows, meta, _session = run_board(interval=0.04)
        self.assertTrue(meta["paginationRepeated"], meta)
        self.assertFalse(meta["coverageComplete"], meta)

    def test_paced_collector_proves_distinct_pages_to_boundary(self):
        rows, meta, session = run_board(interval=ice.DEFAULT_MIN_REQUEST_INTERVAL_SECONDS)
        self.assertFalse(meta["paginationRepeated"], meta)
        self.assertEqual(meta["stopReason"], "lookback-exhausted")
        self.assertTrue(meta["coverageComplete"])
        self.assertEqual([p for _at, p in session.requested], [1, 2, 3, 4])
        ids = [r["nttSn"] for r in rows]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 30)

    def test_minimum_request_interval_is_enforced(self):
        _rows, _meta, session = run_board(interval=ice.DEFAULT_MIN_REQUEST_INTERVAL_SECONDS)
        times = [at for at, _page in session.requested]
        gaps = [b - a for a, b in zip(times, times[1:])]
        self.assertTrue(all(g >= ice.DEFAULT_MIN_REQUEST_INTERVAL_SECONDS for g in gaps), gaps)

    def test_first_request_has_no_wait(self):
        clock = FakeClock()
        with mock.patch.object(ice, "_LAST_ICE_REQUEST_AT", None), \
                mock.patch.object(ice, "MIN_REQUEST_INTERVAL_SECONDS", 12.5), \
                mock.patch.object(ice.time, "monotonic", clock.monotonic), \
                mock.patch.object(ice.time, "sleep", clock.sleep):
            self.assertEqual(ice.pace_ice_request(), 0.0)
            clock.now += 5
            self.assertAlmostEqual(ice.pace_ice_request(), 7.5)
            clock.now += 20
            self.assertEqual(ice.pace_ice_request(), 0.0)

    def test_every_ice_request_helper_is_paced(self):
        for function in (
            ice.fetch, ice.fetch_paging_form, ice.bootstrap_board_session
        ):
            self.assertIn("pace_ice_request()", inspect.getsource(function), function.__name__)
        self.assertNotIn("time.sleep(0.04)", inspect.getsource(ice.scrape_board))

    def test_cli_supports_interval_override(self):
        self.assertIn("--min-request-interval-seconds", inspect.getsource(ice.main))


if __name__ == "__main__":
    unittest.main()
