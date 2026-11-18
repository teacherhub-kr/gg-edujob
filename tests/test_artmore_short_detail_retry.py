"""Fail-closed unit contracts for transient short ArtMore detail responses.

No network, browser or repository writes; a 401/403, block/challenge or changed
source ID never receives the narrow additional request.
"""
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

try:
    import playwright.async_api  # noqa: F401
except ImportError:
    # Production installs Playwright in promote-artmore.yml. A pure unit test
    # should not require the browser dependency or its binaries.
    package = types.ModuleType("playwright")
    api = types.ModuleType("playwright.async_api")
    api.async_playwright = lambda: None
    package.async_api = api
    sys.modules["playwright"] = package
    sys.modules["playwright.async_api"] = api

from scripts import promote_artmore_candidate as artmore

URL = "https://www.artmore.kr/sub/recruit/search_view.do?rec_idx=95724"


class FakePage:
    def __init__(self, frames):
        self.frames = frames
        self.calls = 0
        self.url = URL
        self.body = ""

    async def goto(self, url, *, wait_until, timeout):
        assert url == URL
        assert wait_until == "domcontentloaded"
        assert timeout == 45000
        data = self.frames[self.calls]
        self.calls += 1
        self.url = data.get("url", url)
        self.body = data["body"]
        return SimpleNamespace(status=data["status"])

    def locator(self, selector):
        assert selector == "body"
        return self

    async def inner_text(self):
        return self.body


class ArtMoreShortDetailRetryTests(unittest.IsolatedAsyncioTestCase):
    async def test_normal_verified_response_needs_one_navigation(self):
        page = FakePage([{"status": 200, "body": "정상 채용 상세 " * 40}])
        result = await artmore.validate_one_detail(page, URL, "95724")
        self.assertFalse(result["shortBody"])
        self.assertEqual(result["url"], URL)
        self.assertEqual(page.calls, 1)

    async def test_one_short_200_retries_then_strictly_verifies(self):
        page = FakePage([
            {"status": 200, "body": "요약"},
            {"status": 200, "body": "정상 채용 상세 " * 40},
        ])
        with patch.object(artmore.asyncio, "sleep", new_callable=AsyncMock) as sleeper:
            result = await artmore.validate_one_detail(page, URL, "95724")
        sleeper.assert_awaited_once_with(1.0)
        self.assertEqual(page.calls, 2)
        self.assertFalse(result["shortBody"])
        self.assertEqual(result["url"], URL)

    async def test_second_short_body_still_blocks_promotion(self):
        page = FakePage([{"status": 200, "body": "짧음"}] * 2)
        with patch.object(artmore.asyncio, "sleep", new_callable=AsyncMock):
            with self.assertRaisesRegex(RuntimeError, "unexpectedly short after one retry"):
                await artmore.validate_one_detail(page, URL, "95724")
        self.assertEqual(page.calls, 2)

    async def test_http_access_denial_does_not_retry(self):
        for code in (401, 403, 429):
            with self.subTest(code=code):
                page = FakePage([{"status": code, "body": "Forbidden"}])
                with self.assertRaisesRegex(RuntimeError, f"HTTP {code}"):
                    await artmore.validate_one_detail(page, URL, "95724")
                self.assertEqual(page.calls, 1)

    async def test_challenge_does_not_retry(self):
        page = FakePage([{"status": 200, "body": "비정상적인 접근이 감지되었습니다"}])
        with self.assertRaisesRegex(RuntimeError, "human-check/block page"):
            await artmore.validate_one_detail(page, URL, "95724")
        self.assertEqual(page.calls, 1)

    async def test_redirected_source_id_does_not_retry(self):
        page = FakePage([{
            "status": 200, "body": "정상 채용 상세 " * 40,
            "url": "https://www.artmore.kr/sub/recruit/search_view.do?rec_idx=12345",
        }])
        with self.assertRaisesRegex(RuntimeError, "redirected away"):
            await artmore.validate_one_detail(page, URL, "95724")
        self.assertEqual(page.calls, 1)


if __name__ == "__main__":
    unittest.main()
