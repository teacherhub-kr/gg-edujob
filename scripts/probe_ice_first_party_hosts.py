#!/usr/bin/env python3
"""Read-only ICE official host transport diagnosis; never publishes recruitment data.

The ICE infrastructure may serve identical publicly visible information on
different official *.ice.go.kr properties.  A response is NOT a verified board
unless native nttSn IDs are extractable from the actual HTML.
"""
from __future__ import annotations

import hashlib
import json
import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

ENDPOINTS = (
    ("ice-central-primary", "https://www.ice.go.kr/ice/na/ntt/selectNttList.do?bbsId=1981&mi=10997"),
    ("ice-central-safety", "https://safety.ice.go.kr/ice/na/ntt/selectNttList.do?bbsId=1981&mi=10997"),
    ("ice-central-contract", "https://contract.ice.go.kr/ice/na/ntt/selectNttList.do?bbsId=1981&mi=10997"),
    ("ice-afterschool-primary", "https://www.ice.go.kr/afterschool/na/ntt/selectNttList.do?bbsId=1534&mi=10571"),
    ("ice-afterschool-safety", "https://safety.ice.go.kr/afterschool/na/ntt/selectNttList.do?bbsId=1534&mi=10571"),
)
POST_ID_RE = re.compile(r"nttSn\s*[=:,'\"() ]+\s*(\d{5,})", re.I)
META_REFRESH_RE = re.compile(r"<meta[^>]*http-equiv\s*=\s*['\"]?refresh", re.I)


def authorized_ice_host(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and (host == "ice.go.kr" or host.endswith(".ice.go.kr"))


def native_post_ids(html: str) -> list[str]:
    soup = BeautifulSoup(html or "", "html.parser")
    ids = {
        str(link.get("data-id"))
        for link in soup.select("a.nttInfoBtn[data-id]")
        if str(link.get("data-id") or "").isdigit()
    }
    ids.update(POST_ID_RE.findall(html or ""))
    return sorted(ids)


def classify_response(content: bytes, final_url: str, status: int) -> dict:
    text = content.decode("utf-8", errors="replace")
    ids = native_post_ids(text)
    meta_redirect = bool(META_REFRESH_RE.search(text))
    authorized = authorized_ice_host(final_url)
    # Never treat a tiny redirect/placeholder or an empty shell as complete.
    plausible = (
        status == 200 and authorized and not meta_redirect
        and len(content) >= 1024 and len(ids) >= 1
    )
    return {
        "httpStatus": status,
        "responseBytes": len(content),
        "officialHost": authorized,
        "metaRefresh": meta_redirect,
        "nativeIdCount": len(ids),
        "nativeIdDigest": hashlib.sha256(",".join(ids).encode()).hexdigest()[:16] if ids else "",
        "realBoardCandidate": plausible,
        "finalHost": urlparse(final_url).hostname or "",
    }


def main() -> int:
    results = []
    # Only known first-party URLs, never proxies, browser fingerprint spoofing,
    # guessed paths, authorization headers or externally controlled redirects.
    with requests.Session() as session:
        session.headers.update({"User-Agent": "gg-edujob-read-only-ICE-public-proof/1.0"})
        for name, url in ENDPOINTS:
            record = {"surface": name, "requestedHost": urlparse(url).hostname}
            try:
                reply = session.get(url, timeout=(8, 15), allow_redirects=True)
                record.update(classify_response(reply.content, reply.url, reply.status_code))
            except requests.RequestException as exc:
                record.update({"realBoardCandidate": False, "errorType": type(exc).__name__})
            results.append(record)
            print(json.dumps(record, ensure_ascii=False), flush=True)
    print(json.dumps({
        "policy": "first-party-only-read-only-no-publication",
        "candidates": [r["surface"] for r in results if r.get("realBoardCandidate")],
        "totalSurfaces": len(results),
        "provenComplete": False,
        "note": "HTML transport candidate is not a pagination, freshness or official coverage proof",
    }, ensure_ascii=False), flush=True)
    # This probe is informational. Publication gates remain enforced elsewhere.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
