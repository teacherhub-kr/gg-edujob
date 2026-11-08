#!/usr/bin/env python3
"""Read-only ICE central board transport diagnostic; never publishes recruitment data.

Usage: python scripts/probe_incheon_menu_variants.py
A menu variant is only a candidate until the production collector proves complete
pagination and both mandatory boards. Do not treat this probe as a release gate.
"""
from __future__ import annotations

import hashlib
import json
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

BASE = "https://www.ice.go.kr/ice/na/ntt/selectNttList.do"
VARIANTS = (("canonical", "10997"), ("alternate-menu", "10994"), ("menu-omitted", None))


def probe(session: requests.Session, label: str, menu: str | None, page: int) -> dict:
    params = {"bbsId": "1981", "currPage": str(page)}
    if menu is not None:
        params["mi"] = menu
    url = BASE + "?" + urlencode(params)
    result = {"variant": label, "requestedPage": page}
    try:
        response = session.get(url, timeout=(8, 25), allow_redirects=True)
        soup = BeautifulSoup(response.content, "html.parser")
        ids = sorted({
            str(a.get("data-id"))
            for a in soup.select("a.nttInfoBtn[data-id]")
            if str(a.get("data-id")).isdigit()
        })
        result.update(
            httpStatus=response.status_code,
            finalUrl=response.url,
            responseBytes=len(response.content),
            rowCount=len(ids),
            idDigest=hashlib.sha256(",".join(ids).encode()).hexdigest()[:16],
            sampleIds=ids[:3],
            tinyEmpty=(len(response.content) < 200 and not ids),
        )
    except requests.RequestException as exc:
        result["error"] = type(exc).__name__
    return result


def main() -> int:
    with requests.Session() as session:
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; metro-edujob/3.2)",
            "Accept-Language": "ko-KR,ko;q=0.9",
        })
        results = [
            probe(session, label, menu, page)
            for label, menu in VARIANTS
            for page in (1, 2)
        ]
    for result in results:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    viable = []
    for label, _ in VARIANTS:
        first, second = (r for r in results if r["variant"] == label)
        if (
            first.get("httpStatus") == second.get("httpStatus") == 200
            and first.get("rowCount", 0) > 0
            and second.get("rowCount", 0) > 0
            and first["idDigest"] != second["idDigest"]
        ):
            viable.append(label)
    print(json.dumps({"distinctPageCandidates": viable, "productionReady": False}))
    return 0 if viable else 1


if __name__ == "__main__":
    raise SystemExit(main())
