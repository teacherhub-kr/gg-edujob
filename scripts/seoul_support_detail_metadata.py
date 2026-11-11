#!/usr/bin/env python3
"""Recover Seoul SEN support-office list metadata only from matching official detail fields."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

KST = timezone(timedelta(hours=9))
TODAY = datetime.now(KST).date()
DATE_RE = re.compile(r"(20\d{2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{1,2})")


def _norm(value) -> str:
    return re.sub(r"\s+", "", str(value or ""))


def _date(value) -> str:
    match = DATE_RE.search(str(value or ""))
    if not match:
        return ""
    try:
        return datetime(
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
        ).strftime("%Y/%m/%d")
    except ValueError:
        return ""


def _fields(html: str) -> dict[str, str]:
    result: dict[str, str] = {}
    soup = BeautifulSoup(html, "html.parser")
    for tr in soup.find_all("tr"):
        for th in tr.find_all("th"):
            td = th.find_next_sibling("td")
            if td:
                result[th.get_text(" ", strip=True)] = td.get_text(" ", strip=True)
    return result


def exact_registration_from_detail(
    session: requests.Session,
    board_url: str,
    seq: str,
    school: str,
    listed_deadline: str,
) -> str:
    """Return the official registration date only when the exact detail proves identity.

    Safety contract:
    - the board must be a *.sen.go.kr support-office board;
    - the detail ID must be numeric and fetched from that same host;
    - institution must exactly match the list institution after whitespace normalization;
    - the labelled detail deadline must exist and agree with the list deadline when present;
    - the labelled detail registration date must be valid and not future-dated.

    Any ambiguity returns an empty string so callers remain fail-closed.
    """
    parsed = urlparse(str(board_url or ""))
    host = (parsed.hostname or "").lower()
    if not host.endswith(".sen.go.kr") or not str(seq or "").isdecimal():
        return ""

    detail_url = f"https://{host}/FUS/JO/JOV11.do"
    try:
        response = session.post(
            detail_url,
            data={"job_seq": str(seq)},
            headers={"Referer": board_url},
            timeout=12,
        )
        response.raise_for_status()
        if not response.encoding or response.encoding.lower() == "iso-8859-1":
            response.encoding = response.apparent_encoding or "utf-8"
    except requests.RequestException:
        return ""

    values = _fields(response.text)
    registered = _date(values.get("등록일자") or values.get("등록일"))
    detail_deadline = _date(values.get("마감일자") or values.get("마감일"))
    institution = _norm(values.get("기관명") or values.get("학교명"))
    expected_institution = _norm(school)
    expected_deadline = _date(listed_deadline)

    if not registered or registered > TODAY.strftime("%Y/%m/%d"):
        return ""
    if not institution or not expected_institution or institution != expected_institution:
        return ""
    if not detail_deadline:
        return ""
    if expected_deadline and detail_deadline != expected_deadline:
        return ""
    return registered
