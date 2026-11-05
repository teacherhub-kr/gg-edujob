#!/usr/bin/env python3
"""Read-only diagnostic for ICE central page-2 contract; never publishes listings."""
from __future__ import annotations

import json
import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from merge_incheon_official import (
    REQUIRED_BOARDS, SESSION, build_session, fetch_with_one_explicit_retry,
    parse_table_rows, with_page,
)

BOARD = next(board for board in REQUIRED_BOARDS if board["key"] == "central")


def get_url(param: str, page: int) -> str:
    url = urlparse(BOARD["url"])
    qs = parse_qs(url.query, keep_blank_values=True)
    qs[param] = [str(page)]
    return urlunparse((url.scheme, url.netloc, url.path, url.params, urlencode(qs, doseq=True), url.fragment))


def classify(name: str, response, baseline_ids: set[str]) -> dict:
    rows, meta = parse_table_rows(response.text, response.url, 90, BOARD)
    ids = [str(x) for x in meta["pageIds"]]
    observed = re.search(r"페이지\s*(\d+)\s*/\s*(\d+)", meta.get("pageText", ""))
    return {
        "candidate": name, "http": response.status_code,
        "rawRows": meta["rawRows"], "pageIndicator": observed.group(1) if observed else None,
        "firstTwoIds": ids[:2],
        "distinctFromPageOne": bool(ids) and not set(ids).intersection(baseline_ids),
        "sameAsPageOne": bool(ids) and set(ids) == baseline_ids,
        "finalHost": urlparse(response.url).hostname,
    }


def main():
    results = []
    first = fetch_with_one_explicit_retry(with_page(BOARD["url"], 1))
    base_ids = set(parse_table_rows(first.text, first.url, 90, BOARD)[1]["pageIds"])
    if not base_ids:
        raise SystemExit("FAIL: ICE central page 1 has no parseable official IDs")
    print("BASELINE", json.dumps({"rawIds": len(base_ids), "firstTwoIds": sorted(base_ids)[:2]}, ensure_ascii=False), flush=True)
    for parameter in ("currPage", "pageIndex", "pageNo", "currentPage", "page"):
        try:
            response = fetch_with_one_explicit_retry(get_url(parameter, 2))
            report = classify("GET "+parameter, response, base_ids)
        except Exception as exc:
            report = {"candidate": "GET "+parameter, "errorType": type(exc).__name__}
        results.append(report)
        print("PROBE", json.dumps(report, ensure_ascii=False), flush=True)
    for parameter in ("currPage", "pageIndex"):
        try:
            response = SESSION.post(
                BOARD["url"],
                data={"bbsId": BOARD["bbsId"], "mi": BOARD["mi"], parameter: "2"},
                headers={"Referer": BOARD["url"]},
                timeout=(8, 25), allow_redirects=True,
            )
            response.raise_for_status()
            report = classify("POST "+parameter, response, base_ids)
        except Exception as exc:
            report = {"candidate": "POST "+parameter, "errorType": type(exc).__name__}
        results.append(report)
        print("PROBE", json.dumps(report, ensure_ascii=False), flush=True)
    valid = [x for x in results if x.get("distinctFromPageOne") and x.get("rawRows", 0) > 0]
    print("VALID_PAGE_TWO", json.dumps([x["candidate"] for x in valid], ensure_ascii=False), flush=True)
    if not valid:
        raise SystemExit("FAIL CLOSED: no independently distinct, parseable second page")


if __name__ == "__main__":
    main()
