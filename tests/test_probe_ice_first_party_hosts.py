"""Offline ICE mirror transport fixtures; no source requests in unit tests."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import probe_ice_first_party_hosts as p


class IceFirstPartyTransportTest(unittest.TestCase):
    def test_real_first_party_board_requires_native_post_id(self):
        html = ("<html><head><title>채용</title></head><body>" +
                ("내용" * 600) +
                '<a class="nttInfoBtn" data-id="3389669">인천 교육청 공식 채용</a>' +
                "</body></html>")
        result = p.classify_response(html.encode(), "https://safety.ice.go.kr/ice/na/ntt/selectNttList.do", 200)
        self.assertTrue(result["realBoardCandidate"])
        self.assertEqual(result["nativeIdCount"], 1)

    def test_tiny_meta_redirect_is_never_real_board(self):
        body = b'<meta http-equiv="refresh" content="0; url=https://www.ice.go.kr/law/main.do">'
        result = p.classify_response(body, "https://www.ice.go.kr/ice/na/ntt/selectNttList.do", 200)
        self.assertFalse(result["realBoardCandidate"])
        self.assertTrue(result["metaRefresh"])
        self.assertEqual(result["nativeIdCount"], 0)

    def test_official_host_must_be_https_and_subdomain(self):
        self.assertTrue(p.authorized_ice_host("https://contract.ice.go.kr/ice/main.do"))
        self.assertFalse(p.authorized_ice_host("http://www.ice.go.kr/ice/main.do"))
        self.assertFalse(p.authorized_ice_host("https://ice.go.kr.attacker.example/path"))
        self.assertFalse(p.authorized_ice_host("https://ice-gov.example/"))

    def test_empty_or_wrong_status_is_not_board(self):
        body = b"<html><body>" + b"no ids" * 400 + b"</body></html>"
        self.assertFalse(p.classify_response(body,"https://www.ice.go.kr/",200)["realBoardCandidate"])
        self.assertFalse(p.classify_response(
            (b"<a class='nttInfoBtn' data-id='3389669'>x</a>" + b"x" * 1500),
            "https://www.ice.go.kr/",403)["realBoardCandidate"])

    def test_never_claim_full_collection(self):
        # This is a single-page transport probe; full 2+5 board and 90d
        # reconciliation checks remain mandatory in existing P0 workflow.
        self.assertEqual(len(p.ENDPOINTS), 5)
        self.assertTrue(all(p.authorized_ice_host(url) for _, url in p.ENDPOINTS))


if __name__ == "__main__":
    unittest.main()
