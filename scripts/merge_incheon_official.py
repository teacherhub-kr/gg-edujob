#!/usr/bin/env python3
"""Collect the Incheon Metropolitan Office of Education recruitment board.

The official board exposes each recruitment row through ``a.nttInfoBtn[data-id]``.  That native
``data-id`` is the board's nttSn and is therefore the stable identity used by this collector.
Production traversal is fail-closed: a network error, repeated page, malformed row population, or
emergency page ceiling never counts as complete evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from source_registry import official_source_count
from stable_source_identity import canonical_source_id

ROOT = Path(__file__).resolve().parents[1]
JOBS_PATH = ROOT / "jobs.json"
REPORT_PATH = ROOT / "incheon_official_report.json"
SOURCES_PATH = ROOT / "sources.json"
KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)
SOURCE_NAME = "인천광역시교육청 채용공고"
LIST_URL = "https://www.ice.go.kr/ice/na/ntt/selectNttList.do?bbsId=1981&mi=10997"
DETAIL_PATH = "/ice/na/ntt/selectNttInfo.do"
BBS_ID = "1981"
MI = "10997"
UA = "Mozilla/5.0 (compatible; metro-edujob/3.1; public recruitment aggregator)"
DATE_RE = re.compile(r"(20\d{2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{1,2})")
EXCLUDE_WORDS = re.compile(
    r"최종\s*합격|합격자|서류\s*심사|서류전형|면접\s*대상|선정\s*결과|"
    r"채용\s*결과|전형\s*결과|합격\s*공고|인사\s*발령"
)

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.6"})
RETRY = Retry(
    total=3,
    connect=3,
    read=3,
    status=3,
    backoff_factor=0.8,
    status_forcelist=(408, 429, 500, 502, 503, 504),
    allowed_methods=frozenset(("GET",)),
    respect_retry_after_header=True,
    raise_on_status=False,
)
SESSION.mount("https://", HTTPAdapter(max_retries=RETRY))
SESSION.mount("http://", HTTPAdapter(max_retries=RETRY))


def clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def date_norm(value) -> str:
    match = DATE_RE.search(str(value or ""))
    if not match:
        return ""
    return f"{int(match.group(1)):04d}/{int(match.group(2)):02d}/{int(match.group(3)):02d}"


def as_date(value):
    value = date_norm(value)
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y/%m/%d").replace(tzinfo=KST)
    except ValueError:
        return None


def recent_enough(value, days: int) -> bool:
    dt = as_date(value)
    return dt is None or dt >= NOW - timedelta(days=days)


def with_page(url: str, page: int) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    query["currPage"] = [str(page)]
    return urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, urlencode(query, doseq=True), parsed.fragment)
    )


def fetch(url: str):
    response = SESSION.get(url, timeout=(8, 25), allow_redirects=True)
    response.raise_for_status()
    if not response.encoding or response.encoding.lower() == "iso-8859-1":
        response.encoding = response.apparent_encoding or "utf-8"
    return response


def table_headers(table):
    best = []
    for row in table.find_all("tr"):
        headers = [clean(cell.get_text(" ", strip=True)) for cell in row.find_all("th")]
        if len(headers) > len(best):
            best = headers
    return best


def detail_ntt_sn(anchor) -> str:
    """Return the source-native nttSn from an Incheon recruitment detail control."""
    data_id = clean(anchor.get("data-id", ""))
    if data_id.isdigit():
        return data_id

    raw = " ".join((anchor.get("href", "") or "", anchor.get("onclick", "") or ""))
    parsed = urlparse(raw if raw.startswith(("http://", "https://")) else LIST_URL)
    query = parse_qs(parsed.query)
    value = str((query.get("nttSn") or [""])[0])
    if value.isdigit():
        return value
    match = re.search(r"nttSn\s*[=:,'\"() ]+\s*(\d{4,})", raw, re.IGNORECASE)
    return match.group(1) if match else ""


def detail_url(ntt_sn: str) -> str:
    return f"https://www.ice.go.kr{DETAIL_PATH}?bbsId={BBS_ID}&mi={MI}&nttSn={ntt_sn}"


def guess_level(school: str, title: str) -> str:
    text = f"{school} {title}"
    if "유치원" in text or "병설유" in text:
        return "유치원"
    if "초등학교" in text or re.search(r"[가-힣]+초\b", text):
        return "초등학교"
    if "중학교" in text or re.search(r"[가-힣]+중\b", text):
        return "중학교"
    if "고등학교" in text or re.search(r"[가-힣]+고\b", text):
        return "고등학교"
    if "교육지원청" in text or "교육청" in text:
        return "교육행정기관"
    return "기타"


def guess_type(raw: str, title: str) -> str:
    text = f"{raw} {title}"
    if "기간제교사" in text or "기간제교원" in text or "계약제교원" in text:
        return "기간제교원"
    if "시간강사" in text or "강사" in text or "튜터" in text:
        return "시간강사/강사"
    if "교육공무직" in text or "근로자" in text or "조리" in text or "돌봄" in text:
        return "교육공무직/기간제근로자"
    if "자원봉사" in text or "봉사자" in text or "배움터지킴이" in text:
        return "자원봉사"
    if "신규교사" in text or "정규" in text:
        return "정규채용"
    return "기타"


def pick(values: dict, *names: str) -> str:
    for name in names:
        for key, value in values.items():
            if name in key and value:
                return clean(value)
    return ""


def parse_table_rows(html: str, page_url: str, lookback_days: int):
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    raw_rows = 0
    dated_rows = 0
    page_dates = []
    page_ids = []

    for table in soup.find_all("table"):
        headers = table_headers(table)
        if "등록일" not in headers or "제목" not in headers:
            continue
        for tr in table.find_all("tr"):
            cells = tr.find_all("td", recursive=False)
            if not cells:
                continue
            anchor = tr.select_one("a.nttInfoBtn[data-id]")
            if anchor is None:
                continue
            ntt_sn = detail_ntt_sn(anchor)
            if not ntt_sn:
                continue

            raw_rows += 1
            page_ids.append(ntt_sn)
            values = {
                headers[index]: clean(cell.get_text(" ", strip=True))
                for index, cell in enumerate(cells)
                if index < len(headers) and headers[index]
            }
            registered = date_norm(pick(values, "등록일"))
            if registered:
                dated_rows += 1
                page_dates.append(registered)
            if registered and not recent_enough(registered, lookback_days):
                continue

            title = clean(anchor.get("title") or anchor.find("em").get_text(" ", strip=True) if anchor.find("em") else anchor.get_text(" ", strip=True))
            title = re.sub(r"^N\s*", "", title).strip()
            if not title or EXCLUDE_WORDS.search(title):
                continue

            school = pick(values, "기관명", "학교명")
            raw_type = pick(values, "모집직종", "직종")
            apply_end = date_norm(pick(values, "모집종료일", "접수마감일", "마감일"))
            work_start = date_norm(pick(values, "채용시작일"))
            work_end = date_norm(pick(values, "채용종료일"))
            status = pick(values, "모집상태")
            url = detail_url(ntt_sn)
            rows.append({
                "id": f"ice-{ntt_sn}",
                "province": "인천",
                "school": school or "인천광역시교육청",
                "title": title,
                "subject": "",
                "region": "",
                "regions": [],
                "type": guess_type(raw_type, title),
                "schoolLevel": guess_level(school, title),
                "applyStart": "",
                "applyEnd": apply_end,
                "workStart": work_start,
                "workEnd": work_end,
                "registered": registered,
                "headcount": "",
                "source": SOURCE_NAME,
                "checkedSources": [SOURCE_NAME],
                "sourceType": "통합게시판",
                "recruitmentStatus": status,
                "url": url,
                "nttSn": ntt_sn,
                "bbsId": BBS_ID,
            })

    return rows, {
        "rawRows": raw_rows,
        "datedRows": dated_rows,
        "pageDates": page_dates,
        "pageIds": page_ids,
        "pageText": clean(soup.get_text(" ", strip=True))[:5000],
        "pageUrl": page_url,
    }


def scrape_incheon_central(lookback_days: int = 90, max_pages: int = 1000, check_only: bool = False):
    all_rows = []
    seen_ids = set()
    previous_signature = None
    pages_scanned = 0
    stop_reason = ""
    access_error = ""

    for page in range(1, max_pages + 1):
        page_url = with_page(LIST_URL, page)
        try:
            response = fetch(page_url)
        except Exception as exc:
            access_error = f"{type(exc).__name__}: {str(exc)[:160]}"
            break

        pages_scanned += 1
        rows, meta = parse_table_rows(response.text, response.url, lookback_days)
        signature = tuple(meta.get("pageIds") or [])
        if signature and signature == previous_signature:
            stop_reason = "repeated-page"
            break
        previous_signature = signature or previous_signature

        for row in rows:
            sid = row.get("id", "")
            if sid and sid not in seen_ids:
                seen_ids.add(sid)
                all_rows.append(row)

        if meta["rawRows"] == 0:
            stop_reason = "empty-page"
            break

        parsed_dates = [as_date(value) for value in meta["pageDates"] if as_date(value) is not None]
        if meta["rawRows"] == meta["datedRows"] and parsed_dates and all(
            dt < NOW - timedelta(days=lookback_days) for dt in parsed_dates
        ):
            stop_reason = "lookback-exhausted"
            break

        if check_only and page >= max_pages:
            stop_reason = "check-page-limit"
            break
        time.sleep(0.04)
    else:
        stop_reason = "emergency-page-ceiling"

    all_rows.sort(key=lambda job: (job.get("registered", ""), job.get("applyEnd", "")), reverse=True)
    coverage_complete = bool(
        not access_error
        and stop_reason in {"empty-page", "lookback-exhausted", "check-page-limit"}
        and all_rows
    )
    if not check_only and stop_reason == "check-page-limit":
        coverage_complete = False

    meta = {
        "name": SOURCE_NAME,
        "url": LIST_URL,
        "lookbackDays": lookback_days,
        "pagesScanned": pages_scanned,
        "count": len(all_rows),
        "coverageComplete": coverage_complete,
        "accessError": access_error,
        "paginationRepeated": stop_reason == "repeated-page",
        "stopReason": stop_reason,
        "latestRegistered": all_rows[0].get("registered", "") if all_rows else "",
        "sampleIds": [job.get("id", "") for job in all_rows[:5]],
    }
    return all_rows, meta


def merge_into_jobs(rows, meta) -> dict:
    payload = json.loads(JOBS_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        raise SystemExit("jobs.json is not a valid publication payload")
    if not meta.get("coverageComplete") or not rows:
        raise SystemExit(f"Refusing Incheon merge without complete official evidence: {meta}")

    kept = [
        job for job in payload["jobs"]
        if not (job.get("province") == "인천" and job.get("source") == SOURCE_NAME)
    ]
    combined = kept + rows
    seen = set()
    deduped = []
    for job in sorted(combined, key=lambda j: (j.get("registered", ""), j.get("applyEnd", "")), reverse=True):
        sid = canonical_source_id(job) or str(job.get("id") or "") or hashlib.sha1(
            json.dumps(job, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        if sid in seen:
            continue
        seen.add(sid)
        strong_id = canonical_source_id(job)
        if strong_id:
            job["sourceIdentity"] = strong_id
        deduped.append(job)

    payload["jobs"] = deduped
    sources = payload.setdefault("sources", {})
    sources["incheon"] = {
        "central": {
            "name": SOURCE_NAME,
            "url": LIST_URL,
            "count": len(rows),
            "ok": True,
            "state": "ok",
            "coverageComplete": True,
            "pagesScanned": meta.get("pagesScanned"),
        },
        "supportOffices": [],
    }
    payload["officialSourceCount"] = official_source_count()
    JOBS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def write_report(meta, rows, merged: bool) -> None:
    report = {
        "generatedAt": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST"),
        **meta,
        "merged": bool(merged),
        "officialSample": [
            {
                "id": row.get("id"),
                "school": row.get("school"),
                "title": row.get("title"),
                "registered": row.get("registered"),
                "url": row.get("url"),
            }
            for row in rows[:3]
        ],
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lookback-days", type=int, default=90)
    parser.add_argument("--max-pages", type=int, default=1000)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    sources = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    central = ((sources.get("incheon") or {}).get("central") or {}) if isinstance(sources, dict) else {}
    if central.get("url") != LIST_URL or central.get("name") != SOURCE_NAME:
        raise SystemExit("Incheon official source is absent or differs from the canonical registry entry")

    rows, meta = scrape_incheon_central(
        lookback_days=args.lookback_days,
        max_pages=args.max_pages,
        check_only=args.check_only,
    )
    if not rows:
        raise SystemExit(f"No Incheon official recruitment rows parsed: {meta}")
    if meta.get("accessError") or meta.get("paginationRepeated"):
        raise SystemExit(f"Incheon official traversal is not trustworthy: {meta}")
    if args.check_only:
        write_report(meta, rows, merged=False)
        print(json.dumps(meta, ensure_ascii=False))
        return 0
    if not meta.get("coverageComplete"):
        raise SystemExit(f"Incheon official lookback traversal incomplete: {meta}")

    merge_into_jobs(rows, meta)
    write_report(meta, rows, merged=True)
    print(json.dumps(meta, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
