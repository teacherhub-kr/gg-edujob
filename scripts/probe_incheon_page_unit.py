#!/usr/bin/env python3
"""Read-only probe: can an ICE board return a whole lookback window on page 1?

Hypothesis (P0, 2026-11-08): the central ICE board (bbsId=1981) now ignores
currPage on page 2+, both as GET query and pagingForm POST, while the same CMS
still serves page 1 correctly. Standard eGovFrame boards often accept a page
size parameter (pageUnit / recordCountPerPage / ...). If one is honored, the
complete lookback window can be read from page 1 without any page-2 request.

This probe never writes jobs.json or any production report. It records only
public posting IDs (nttSn), counts, dates, response sizes and form field
*names*; cookie, token and form values are never logged.

A variant is reported as `coverageCandidate` only when all of these hold:
  * HTTP 200 and parseable rows
  * strictly more rows than the default page 1, all IDs unique
  * the default page-1 IDs are the exact head of the variant (same order)
  * dates are non-increasing (newest first)
  * the window is closed: the oldest row is older than the lookback window, or
    the board's displayed total count is fully returned
It is still only a candidate: production adoption needs a separate PR with a
traversal contract and a cross-check against an independent ID source.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
import merge_incheon_official as ice  # noqa: E402  (read-only reuse of parser/session)

KST = timezone(timedelta(hours=9))
PAGE_SIZE_PARAMETERS = ("pageUnit", "recordCountPerPage", "listCnt", "pageSize", "rowCnt", "numOfRows")
TOTAL_RE = re.compile(r"(?:총|전체)\s*(?:게시물\s*)?[:：]?\s*([0-9][0-9,]*)\s*건")
DEFAULT_REPORT = Path("incheon_page_unit_probe_report.json")


def with_query(url: str, **params: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    for key, value in params.items():
        query[key] = [str(value)]
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, urlencode(query, doseq=True), parsed.fragment))


def paging_form(html: str, page_url: str):
    soup = BeautifulSoup(html, "html.parser")
    form = soup.find("form", attrs={"name": "pagingForm"}) or soup.find("form", attrs={"id": "pagingForm"})
    if form is None:
        return None
    fields = []
    for element in form.find_all(["input", "select", "textarea"]):
        name = element.get("name")
        if name:
            fields.append((name, str(element.get("value") or "")))
    action = urljoin(page_url, form.get("action") or page_url)
    return {"action": action, "method": (form.get("method") or "get").lower(), "fields": fields}


def displayed_total(html: str):
    match = TOTAL_RE.search(BeautifulSoup(html, "html.parser").get_text(" ", strip=True))
    return int(match.group(1).replace(",", "")) if match else None


def summarize(html: str, url: str, board: dict, status: int, method: str, label: str) -> dict:
    _rows, meta = ice.parse_table_rows(html, url, 36500, board)
    ids = [str(value) for value in meta.get("pageIds", [])]
    # The collector emits "YYYY/MM/DD"; compare real dates, never strings.
    dates = [d.date().isoformat() for d in (ice.as_date(value) for value in meta.get("pageDates", [])) if d]
    return {
        "label": label,
        "method": method,
        "status": status,
        "bytes": len(html.encode("utf-8")),
        "rows": len(ids),
        "uniqueIds": len(set(ids)),
        "ids": ids,
        "newest": max(dates) if dates else "",
        "oldest": min(dates) if dates else "",
        "datesNonIncreasing": all(a >= b for a, b in zip(dates, dates[1:])),
        "displayedTotal": displayed_total(html),
    }


def judge(baseline: dict, variant: dict, lookback_days: int, today) -> dict:
    head = baseline["ids"]
    reasons = []
    if variant["status"] != 200:
        reasons.append("http-status")
    if variant["rows"] <= baseline["rows"]:
        reasons.append("page-size-not-honored")
    if variant["uniqueIds"] != variant["rows"]:
        reasons.append("duplicate-ids")
    if variant["ids"][: len(head)] != head:
        reasons.append("default-page-not-head")
    if not variant["datesNonIncreasing"]:
        reasons.append("dates-not-newest-first")
    cutoff = (today - timedelta(days=lookback_days)).isoformat()
    closed_by_date = bool(variant["oldest"]) and variant["oldest"] < cutoff
    total = variant["displayedTotal"] or baseline["displayedTotal"]
    closed_by_total = bool(total) and variant["rows"] >= total
    if not (closed_by_date or closed_by_total):
        reasons.append("window-not-closed")
    return {
        "coverageCandidate": not reasons,
        "closedByDate": closed_by_date,
        "closedByTotal": closed_by_total,
        "rejectReasons": reasons,
    }


def compact(entry: dict) -> dict:
    ids = entry.pop("ids")
    entry["firstIds"] = ids[:3]
    entry["lastIds"] = ids[-3:]
    return entry


def probe_board(board: dict, page_size: int, lookback_days: int, today) -> dict:
    ice.reset_session()
    response = ice.SESSION.get(board["url"], timeout=(8, 25), allow_redirects=True)
    baseline = summarize(response.text, str(response.url), board, response.status_code, "GET", "default")
    form = paging_form(response.text, str(response.url))
    result = {
        "board": board["key"],
        "bbsId": board["bbsId"],
        "pagingFormFieldNames": [name for name, _ in form["fields"]] if form else [],
        "baseline": None,
        "variants": [],
    }
    variants = []
    for parameter in PAGE_SIZE_PARAMETERS:
        url = with_query(board["url"], currPage="1", **{parameter: str(page_size)})
        r = ice.SESSION.get(url, timeout=(8, 25), allow_redirects=True)
        variants.append(summarize(r.text, str(r.url), board, r.status_code, "GET", f"GET {parameter}={page_size}"))
        if form and str(form["action"]).startswith("https://") and urlparse(form["action"]).netloc.endswith("ice.go.kr"):
            body = [(name, value) for name, value in form["fields"] if name not in {parameter, "currPage"}]
            body += [("currPage", "1"), (parameter, str(page_size))]
            r = ice.SESSION.post(form["action"], data=body, timeout=(8, 25), allow_redirects=True,
                                 headers={"Referer": str(response.url)})
            variants.append(summarize(r.text, str(r.url), board, r.status_code, "POST",
                                      f"POST pagingForm {parameter}={page_size}"))
    for variant in variants:
        variant.update(judge(baseline, variant, lookback_days, today))
        result["variants"].append(compact(variant))
    result["baseline"] = compact(baseline)
    result["coverageCandidates"] = [v["label"] for v in result["variants"] if v["coverageCandidate"]]
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--page-size", type=int, default=300)
    parser.add_argument("--lookback-days", type=int, default=14)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)
    today = datetime.now(KST).date()
    report = {
        "generatedAt": datetime.now(KST).isoformat(timespec="seconds"),
        "purpose": "read-only ICE page-size probe; never production evidence",
        "pageSize": args.page_size,
        "lookbackDays": args.lookback_days,
        "boards": [],
    }
    for board in ice.REQUIRED_BOARDS:
        try:
            report["boards"].append(probe_board(board, args.page_size, args.lookback_days, today))
        except Exception as exc:  # diagnostic only; keep other board results
            report["boards"].append({"board": board["key"], "error": f"{type(exc).__name__}: {str(exc)[:160]}"})
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for board in report["boards"]:
        print("ICE_PAGE_UNIT", json.dumps({k: board.get(k) for k in ("board", "error", "coverageCandidates")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
