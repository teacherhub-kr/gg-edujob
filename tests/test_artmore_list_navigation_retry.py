"""One-off network-timeout recovery for initial ArtMore list navigation only.

The fake page provides strict request accounting; no browser or live scraping
is required, and second-failure/denial pathways remain fail-closed.
"""
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

try:
    from playwright.async_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError
except ImportError:
    pkg = sys.modules.get("playwright")
    if pkg is None:
        pkg = types.ModuleType("playwright")
        sys.modules["playwright"] = pkg
    api = sys.modules.get("playwright.async_api")
    if api is None:
        api = types.ModuleType("playwright.async_api")
        sys.modules["playwright.async_api"] = api
    if not hasattr(api, "Error"):
        class FakePlaywrightError(Exception):
            pass
        api.Error = FakePlaywrightError
    if not hasattr(api, "TimeoutError"):
        class FakePlaywrightTimeoutError(api.Error):
            pass
        api.TimeoutError = FakePlaywrightTimeoutError
    api.async_playwright = getattr(api, "async_playwright", lambda: None)
    pkg.async_api = api
    PlaywrightError, PlaywrightTimeoutError = api.Error, api.TimeoutError

from scripts import crawl_artmore_browser as crawler


class FakePage:
    def __init__(self, results):
        self.results = results
        self.calls = 0

    async def goto(self, url, *, wait_until, timeout):
        assert url == crawler.URL
        assert wait_until == "domcontentloaded"
        assert timeout == 60000
        result = self.results[self.calls]
        self.calls += 1
        if isinstance(result, Exception):
            raise result
        return SimpleNamespace(status=result)


class ArtMoreListTimeoutRetryContracts(unittest.IsolatedAsyncioTestCase):
    async def test_normal_200_navigation_is_single_attempt(self):
        page = FakePage([200])
        result = await crawler.load_list_with_single_timeout_retry(page)
        self.assertEqual(result.status, 200)
        self.assertEqual(page.calls, 1)

    async def test_net_timeout_single_retry_recovers(self):
        page = FakePage([PlaywrightError("Page.goto: net::ERR_TIMED_OUT"), 200])
        with patch.object(crawler.asyncio, "sleep", new_callable=AsyncMock) as sleeper:
            result = await crawler.load_list_with_single_timeout_retry(page)
        self.assertEqual(result.status, 200)
        self.assertEqual(page.calls, 2)
        sleeper.assert_awaited_once_with(1.0)

    async def test_playwright_timeout_type_single_retry_recovers(self):
        page = FakePage([PlaywrightTimeoutError("Timeout 60000ms exceeded"), 200])
        with patch.object(crawler.asyncio, "sleep", new_callable=AsyncMock):
            result = await crawler.load_list_with_single_timeout_retry(page)
        self.assertEqual(result.status, 200)
        self.assertEqual(page.calls, 2)

    async def test_second_timeout_fails_without_third_request(self):
        page = FakePage([PlaywrightError("Page.goto: net::ERR_TIMED_OUT")] * 2)
        with patch.object(crawler.asyncio, "sleep", new_callable=AsyncMock):
            with self.assertRaises(PlaywrightError):
                await crawler.load_list_with_single_timeout_retry(page)
        self.assertEqual(page.calls, 2)

    async def test_non_timeout_network_error_has_no_retry(self):
        for error in ("net::ERR_ABORTED", "net::ERR_NAME_NOT_RESOLVED", "net::ERR_CONNECTION_REFUSED"):
            with self.subTest(error=error):
                page = FakePage([PlaywrightError("Page.goto: " + error)])
                with self.assertRaises(PlaywrightError):
                    await crawler.load_list_with_single_timeout_retry(page)
                self.assertEqual(page.calls, 1)

    async def test_denial_response_never_causes_extra_initial_navigation(self):
        page = FakePage([403])
        result = await crawler.load_list_with_single_timeout_retry(page)
        self.assertEqual(result.status, 403)
        self.assertEqual(page.calls, 1)


if __name__ == "__main__":
    unittest.main()
