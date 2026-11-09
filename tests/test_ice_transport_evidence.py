import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ice_transport_evidence as ev  # noqa: E402

def fake_response(body: bytes, *, status=200, ctype="text/html", server="",
                  url="https://www.ice.go.kr/x", cookies=(), history=()):
    return SimpleNamespace(
        content=body,
        status_code=status,
        headers={"Content-Type": ctype, "Server": server},
        url=url,
        encoding="utf-8",
        cookies=[SimpleNamespace(name=n, value="SECRET-COOKIE-VALUE") for n in cookies],
        history=[SimpleNamespace(url=u) for u in history],
    )

class TransportEvidenceTests(unittest.TestCase):
    def test_script_redirect_is_classified_and_query_redacted(self):
        body = b"<script>location.href='https://www.ice.go.kr/err.html?sid=abc123';</script>"
        fp = ev.transport_fingerprint(fake_response(body))
        self.assertEqual(fp["bodyKind"], "script-redirect")
        self.assertIn("https://www.ice.go.kr/err.html?<query-redacted>", fp["bodyExcerpt"])
        self.assertNotIn("abc123", fp["bodyExcerpt"])

    def test_block_notice_korean_and_english(self):
        for body in ("<html>해외 IP는 접근이 제한됩니다</html>", "<h1>Access Denied</h1>", "요청이 차단되었습니다"):
            self.assertEqual(ev.classify_body(body), "block-notice", body)

    def test_empty_and_other(self):
        self.assertEqual(ev.classify_body("   "), "empty")
        self.assertEqual(ev.classify_body("<html><body></body></html>"), "other")

    def test_token_like_runs_and_cookie_values_never_recorded(self):
        token = "A" * 24 + "b9_-" + "Z" * 10
        fp = ev.transport_fingerprint(
            fake_response(f"<input value='{token}'>".encode(), cookies=("JSESSIONID", "WMONID"))
        )
        self.assertNotIn(token, fp["bodyExcerpt"])
        self.assertIn("<redacted:", fp["bodyExcerpt"])
        self.assertEqual(fp["setCookieNames"], ["JSESSIONID", "WMONID"])
        self.assertNotIn("SECRET-COOKIE-VALUE", repr(fp))

    def test_large_bodies_get_metadata_only(self):
        fp = ev.transport_fingerprint(fake_response(b"x" * (ev.MAX_EXCERPT_SOURCE_BYTES + 1)))
        self.assertNotIn("bodyExcerpt", fp)
        self.assertNotIn("bodyKind", fp)

    def test_redirect_chain_and_server_are_recorded(self):
        fp = ev.transport_fingerprint(fake_response(
            b"", server="WAF-Edge", url="https://block.example.kr/",
            history=("https://www.ice.go.kr/ice/na/ntt/selectNttList.do?bbsId=1981",)))
        self.assertEqual(fp["redirectCount"], 1)
        self.assertEqual(fp["redirectHosts"], ["www.ice.go.kr"])
        self.assertEqual(fp["finalHost"], "block.example.kr")
        self.assertEqual(fp["server"], "WAF-Edge")
        self.assertEqual(fp["bodyKind"], "empty")

    def test_summary_puts_classification_before_truncatable_metadata(self):
        summary = ev.transport_summary(fake_response(b"<h1>Forbidden</h1>", status=200))
        self.assertTrue(summary.startswith("kind=block-notice excerpt="), summary)

class CollectorWiringTests(unittest.TestCase):
    def test_support_collector_tiny_placeholder_error_carries_fingerprint(self):
        import collect_incheon_support as support
        response = fake_response(b"<script>location.replace('/')</script>")
        response.raise_for_status = lambda: None
        with self.assertRaises(support.requests.RequestException) as ctx:
            support._normalize_response(response)
        self.assertIn("kind=script-redirect", str(ctx.exception))

    def test_nambu_non_json_error_carries_fingerprint(self):
        source = (ROOT / "scripts/collect_incheon_support.py").read_text(encoding="utf-8")
        self.assertIn('f"Nambu API non-JSON: {transport_summary(response)}"', source)
        self.assertNotIn("str(exc)[:180]", source)

    def test_central_collector_attaches_fingerprint_to_tiny_pages(self):
        source = (ROOT / "scripts/merge_incheon_official.py").read_text(encoding="utf-8")
        self.assertIn('page_response_evidence[-1]["transport"] = transport_fingerprint(response)', source)
        self.assertIn('if len(response.content or b"") <= MAX_EXCERPT_SOURCE_BYTES:', source)

if __name__ == "__main__":
    unittest.main()
