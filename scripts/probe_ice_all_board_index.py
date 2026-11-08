#!/usr/bin/env python3
"""Read-only proof for the official ICE all-board index.

This diagnostic never writes production data. It verifies whether the GitHub runner
can read current bbsId=1981 recruitment rows, traverse a distinct second index page,
and open an exact official detail link while the primary ICE list path is degraded.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

INDEX_URL = "https://iwee.ice.go.kr/ontong/na/ntt/selectAllNttList.do"
DETAIL_PATH = "/ice/na/ntt/selectNttInfo.do"
RECRUITMENT_BOARD = "1981"
ALLOWED_HOST = "iwee.ice.go.kr"
DATE_RE = re.compile(r"\b(20\d{2})[-./](\d{1,2})[-./](\d{1,2})\b")


def exact_items(html: str, base_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict] = []
    for anchor in soup.find_all("a", href=True):
        absolute = urljoin(base_url, anchor["href"])
        parsed = urlparse(absolute)
        query = parse_qs(parsed.query)
        board = (query.get("bbsId") or [""])[0]
        notice = (query.get("nttSn") or [""])[0]
        if (
            parsed.hostname != ALLOWED_HOST
            or parsed.path != DETAIL_PATH
            or not board.isdigit()
            or not notice.isdigit()
        ):
            continue
        row = anchor.find_parent("tr")
        cells = row.find_all("td") if row else []
        posted_text = cells[-1].get_text(" ", strip=True) if cells else ""
        match = DATE_RE.search(posted_text)
        posted = None
        if match:
            posted = date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        items.append({
            "bbsId": board,
            "nttSn": notice,
            "posted": posted,
            "url": absolute,
        })
    deduped = {}
    for item in items:
        deduped[(item["bbsId"], item["nttSn"])] = item
    return list(deduped.values())


def paging_submission(html: str, response_url: str) -> tuple[str, list[tuple[str, str]], list[str]]:
    soup = BeautifulSoup(html, "html.parser")
    form = soup.find("form", attrs={"name": "pagingForm"})
    if form is None:
        raise ValueError("official all-board index has no pagingForm")
    target = urljoin(response_url, str(form.get("action") or ""))
    parsed = urlparse(target)
    if parsed.hostname != ALLOWED_HOST or parsed.path != "/ontong/na/ntt/selectAllNttList.do":
        raise ValueError("unexpected all-board paging endpoint")
    fields: list[tuple[str, str]] = []
    for element in form.find_all(["input", "select"]):
        name = element.get("name")
        if not name or str(element.get("type") or "").lower() in {"submit", "button", "image"}:
            continue
        value = "2" if name == "currPage" else str(element.get("value") or "")
        fields.append((name, value))
    if not any(name == "currPage" for name, _ in fields):
        fields.append(("currPage", "2"))
    return target, fields, sorted({name for name, _ in fields})


def require_real(response: requests.Response, label: str) -> None:
    response.raise_for_status()
    if len(response.content) < 1000:
        raise RuntimeError(f"{label} returned tiny placeholder body ({len(response.content)} bytes)")


def main() -> None:
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; EdujobReadOnlyProof/1.0)"})
    first = session.get(INDEX_URL, timeout=(8, 30), allow_redirects=True)
    require_real(first, "all-board page 1")
    first_items = exact_items(first.text, first.url)
    first_ids = {(item["bbsId"], item["nttSn"]) for item in first_items}
    recruitment = [item for item in first_items if item["bbsId"] == RECRUITMENT_BOARD]
    recent_cutoff = date.today() - timedelta(days=14)
    recent_recruitment = [
        item for item in recruitment if item["posted"] is not None and item["posted"] >= recent_cutoff
    ]
    if not first_ids:
        raise SystemExit("FAIL CLOSED: official all-board page 1 has no exact IDs")
    if not recent_recruitment:
        raise SystemExit("FAIL CLOSED: no current bbsId=1981 recruitment row in 14-day window")

    detail = session.get(recent_recruitment[0]["url"], timeout=(8, 30), allow_redirects=True)
    require_real(detail, "exact recruitment detail")
    detail_query = parse_qs(urlparse(detail.url).query)
    if (detail_query.get("bbsId") or [""])[0] != RECRUITMENT_BOARD:
        raise SystemExit("FAIL CLOSED: detail redirect lost bbsId=1981")
    if (detail_query.get("nttSn") or [""])[0] != recent_recruitment[0]["nttSn"]:
        raise SystemExit("FAIL CLOSED: detail redirect lost exact nttSn")

    target, fields, field_names = paging_submission(first.text, first.url)
    second = session.post(
        target,
        data=fields,
        headers={"Referer": first.url},
        timeout=(8, 30),
        allow_redirects=True,
    )
    require_real(second, "all-board page 2")
    second_items = exact_items(second.text, second.url)
    second_ids = {(item["bbsId"], item["nttSn"]) for item in second_items}
    if not second_ids or first_ids == second_ids or not (second_ids - first_ids):
        raise SystemExit("FAIL CLOSED: all-board page 2 did not produce distinct exact IDs")

    report = {
        "generatedAt": datetime.now().astimezone().isoformat(),
        "readOnly": True,
        "pageOneExactIds": len(first_ids),
        "pageTwoExactIds": len(second_ids),
        "distinctPageTwoIds": len(second_ids - first_ids),
        "pageOneRecruitmentIds": len(recruitment),
        "recentRecruitmentIds": len(recent_recruitment),
        "latestRecruitmentDate": max(item["posted"] for item in recent_recruitment).isoformat(),
        "sampleExactIdentity": {
            "bbsId": RECRUITMENT_BOARD,
            "nttSn": recent_recruitment[0]["nttSn"],
        },
        "pagingFieldNames": field_names,
    }
    print("ICE_ALL_BOARD_PROOF", json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
