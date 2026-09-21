#!/usr/bin/env python3
"""Collect all five official Incheon education-support-office recruitment boards.

The registry contains the five official support offices. Three currently have reviewed board URLs
(Bukbu, Dongbu, Ganghwa). Nambu and Seobu are discovered only from their official homepages; an
unverified guessed URL is never accepted. Every office must either prove a complete traversal to
the requested lookback boundary or fail closed.

Rows keep exact official detail URLs and source-native identities. Cross-posted rows already
published from the Incheon metropolitan central board are collapsed only when school, normalized
title and registration date agree; the support-office source identity is retained in
sourceIdentities/sourceOccurrences so reconciliation can still prove every official source.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from stable_source_identity import canonical_source_id
from support_population_contract import is_support_population_job

ROOT = Path(__file__).resolve().parents[1]
SOURCES_PATH = ROOT / "sources.json"
JOBS_PATH = ROOT / "jobs.json"
REPORT_PATH = ROOT / "incheon_support_report.json"
KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)

UA = "Mozilla/5.0 (compatible; metro-edujob-incheon-support/1.0; public recruitment aggregator)"
DATE_RE = re.compile(r"(?:(20)?(\d{2}))\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{1,2})")
JOB_WORDS = re.compile(
    r"채용|구인|모집|기간제|계약제|시간강사|강사|교사|교원|공무직|근로자|조리|"
    r"돌봄|보조인력|봉사|튜터|안전지킴이|코디네이터|전문상담|영양"
)
EXCLUDE_WORDS = re.compile(
    r"최종\s*합격|합격자|서류\s*심사|서류전형|면접\s*대상|선정\s*결과|"
    r"채용\s*결과|전형\s*결과|합격\s*공고|접수\s*현황|인사\s*발령"
)
BOARD_WORDS = re.compile(r"채용\s*공고|구인\s*/?\s*구직|구인|채용")
DETAIL_HINT = re.compile(r"view|detail|read|bbsmsgdetail|recruit|job_offer|joboffer", re.I)
PAGER_WORDS = {"다음", "다음페이지", "next", ">", "›", "»"}

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


def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": UA,
            "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.6",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }
    )
    session.mount("https://", HTTPAdapter(max_retries=RETRY))
    session.mount("http://", HTTPAdapter(max_retries=RETRY))
    return session


SESSION = build_session()


def clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def date_norm(value) -> str:
    text = str(value or "")
    m = DATE_RE.search(text)
    if not m:
        return ""
    year = int(m.group(2))
    if m.group(1):
        year += 2000
    elif year < 80:
        year += 2000
    else:
        year += 1900
    return f"{year:04d}/{int(m.group(3)):02d}/{int(m.group(4)):02d}"


def as_date(value):
    value = date_norm(value)
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y/%m/%d").replace(tzinfo=KST)
    except ValueError:
        return None


def recent_enough(value: str, days: int) -> bool:
    dt = as_date(value)
    return dt is None or dt >= NOW - timedelta(days=days)


def definitely_old(value: str, days: int) -> bool:
    dt = as_date(value)
    return bool(dt and dt < NOW - timedelta(days=days))


def norm_key(value) -> str:
    return re.sub(r"[^0-9a-z가-힣]+", "", clean(value).lower())


def school_from_title(title: str) -> str:
    match = re.search(r"([가-힣A-Za-z0-9·]+(?:유치원|초등학교|중학교|고등학교|학교))", title or "")
    return clean(match.group(1)) if match else ""


def guess_level(school: str, title: str) -> str:
    text = f"{school} {title}"
    if "유치원" in text or "병설유" in text:
        return "유치원"
    if "초등학교" in text:
        return "초등학교"
    if "중학교" in text:
        return "중학교"
    if "고등학교" in text:
        return "고등학교"
    if "교육지원청" in text or "교육청" in text:
        return "교육행정기관"
    return "기타"


def guess_type(title: str) -> str:
    if re.search(r"기간제\s*(?:교사|교원)|계약제\s*교원", title):
        return "기간제교원"
    if re.search(r"시간강사|강사|튜터|코디네이터", title):
        return "시간강사/강사"
    if re.search(r"교육공무직|기간제\s*근로|근로자|조리|돌봄|보조인력", title):
        return "교육공무직/기간제근로자"
    if re.search(r"자원봉사|봉사자|지킴이", title):
        return "자원봉사"
    return "기타"


def fetch(url: str):
    response = SESSION.get(url, timeout=(8, 25), allow_redirects=True)
    response.raise_for_status()
    if not response.encoding or response.encoding.lower() == "iso-8859-1":
        response.encoding = response.apparent_encoding or "utf-8"
    return response


def allowed_host(url: str, office: dict) -> bool:
    host = (urlparse(url).hostname or "").lower()
    allowed = [str(x).lower() for x in office.get("allowedHosts", []) if x]
    if not allowed:
        base = (urlparse(str(office.get("url") or "")).hostname or "").lower()
        allowed = [base] if base else []
    return bool(host and any(host == item or host.endswith("." + item) for item in allowed))


def discover_support_boards(office: dict) -> tuple[list[str], list[dict]]:
    seeds = [str(x) for x in office.get("boardUrls", []) if x]
    found = []
    evidence = []
    for url in seeds:
        if url not in found:
            found.append(url)
            evidence.append({"url": url, "kind": "registry-seed"})

    if not office.get("autoDiscover", False):
        return found, evidence

    start_urls = [str(office.get("url") or "")]
    visited = set()
    for _depth in range(2):
        next_round = []
        for start in start_urls:
            if not start or start in visited:
                continue
            visited.add(start)
            try:
                response = fetch(start)
            except Exception as exc:
                evidence.append(
                    {"url": start, "kind": "discovery-access-error", "error": f"{type(exc).__name__}: {str(exc)[:140]}"}
                )
                continue
            if not allowed_host(response.url, office):
                evidence.append({"url": response.url, "kind": "discovery-unapproved-host"})
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            for anchor in soup.find_all("a", href=True):
                label = clean(anchor.get_text(" ", strip=True))
                href = clean(anchor.get("href"))
                if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                    continue
                absolute = urljoin(response.url, href)
                if not allowed_host(absolute, office):
                    continue
                if BOARD_WORDS.search(label):
                    if absolute not in found:
                        found.append(absolute)
                        evidence.append({"url": absolute, "kind": "discovered-board", "label": label})
                elif re.search(r"사이트맵|sitemap", label, re.I) and absolute not in visited:
                    next_round.append(absolute)
        start_urls = next_round

    return found, evidence


def headers_for_table(table) -> list[str]:
    best = []
    for tr in table.find_all("tr"):
        # Legacy ICE boards render semantic headers with visual whitespace
        # (for example "제 목"). Normalize that presentation whitespace so
        # schema matching remains exact without broadening the row parser.
        hs = [re.sub(r"\\s+", "", clean(x.get_text(" ", strip=True))) for x in tr.find_all("th")]
        if len(hs) > len(best):
            best = hs
    if best:
        return best

    # Bukbu's legacy list can expose the header row with TD cells instead of
    # TH cells. Accept it only when it matches a reviewed recruitment schema.
    for tr in table.find_all("tr"):
        cells = [re.sub(r"\\s+", "", clean(x.get_text(" ", strip=True))) for x in tr.find_all("td", recursive=False)]
        if len(cells) >= 4 and any(x in {"제목", "자료명"} for x in cells) and any("등록일" in x or "작성일" in x for x in cells):
            return cells
    return []


def row_values(tr, headers: list[str]) -> dict:
    cells = tr.find_all("td", recursive=False)
    return {
        headers[i]: clean(cell.get_text(" ", strip=True))
        for i, cell in enumerate(cells)
        if i < len(headers) and headers[i]
    }


def pick(values: dict, *needles: str) -> str:
    for needle in needles:
        for key, value in values.items():
            if needle in key and value:
                return clean(value)
    return ""


def exact_detail_from_anchor(page_url: str, anchor, office: dict) -> str:
    href = clean(anchor.get("href"))
    if href and not href.lower().startswith(("javascript:", "#")):
        absolute = urljoin(page_url, href)
        if allowed_host(absolute, office):
            parsed = urlparse(absolute)
            query = parse_qs(parsed.query)
            if DETAIL_HINT.search(parsed.path) or any(
                query.get(key)
                for key in ("data_idx", "msg_seq", "nttSn", "idx", "seq", "no", "num", "uid", "boardSeq")
            ):
                return absolute

    data_id = clean(anchor.get("data-id"))
    parsed_page = urlparse(page_url)
    query_page = parse_qs(parsed_page.query)

    # Live Bukbu contract (2026-09-21): the list anchor is href="#" and
    # carries the source-native identity in data-mst/data-idx.
    if (parsed_page.hostname or "").lower() == "bukbu.ice.go.kr":
        data_mst = clean(anchor.get("data-mst"))
        data_idx = clean(anchor.get("data-idx"))
        # ICE native keys are a two-letter prefix plus a zero-padded numeric
        # sequence; the live board currently uses 10 digits but older reviewed
        # fixtures are shorter. Validate the native shape without inventing IDs.
        if re.fullmatch(r"BM\\d{6,}", data_mst, re.I) and re.fullmatch(r"BD\\d{6,}", data_idx, re.I):
            query = {"bbs_mst_idx": data_mst.upper(), "data_idx": data_idx.upper()}
            menu = clean(anchor.get("data-menu")) or str((query_page.get("menu_idx") or [""])[0])
            if menu:
                query["menu_idx"] = menu
            return urlunparse(
                (parsed_page.scheme, parsed_page.netloc, "/bbs/data/view.do", "", urlencode(query), "")
            )

    # Bukbu's legacy list can encode the native BD... identity only inside
    # a javascript/onclick row link. Recover that source-native key rather
    # than synthesizing an unstable row number.
    if (parsed_page.hostname or "").lower() == "bukbu.ice.go.kr":
        raw = " ".join((clean(anchor.get("href")), clean(anchor.get("onclick"))))
        legacy = re.search(r"\\b(BD\\d{6,})\\b", raw, re.I)
        if legacy and query_page.get("bbs_mst_idx"):
            query = {
                "bbs_mst_idx": query_page["bbs_mst_idx"][0],
                "data_idx": legacy.group(1).upper(),
            }
            if query_page.get("menu_idx"):
                query["menu_idx"] = query_page["menu_idx"][0]
            return urlunparse(
                (parsed_page.scheme, parsed_page.netloc, "/bbs/data/view.do", "", urlencode(query), "")
            )

    if data_id and query_page.get("bbs_mst_idx"):
        query = {
            "bbs_mst_idx": query_page["bbs_mst_idx"][0],
            "data_idx": data_id,
        }
        if query_page.get("menu_idx"):
            query["menu_idx"] = query_page["menu_idx"][0]
        return urlunparse(
            (parsed_page.scheme, parsed_page.netloc, "/bbs/data/view.do", "", urlencode(query), "")
        )

    raw = " ".join((href, clean(anchor.get("onclick"))))
    quoted = re.findall(r"['\"]([^'\"]+)['\"]", raw)
    for item in quoted:
        if "/" not in item:
            continue
        absolute = urljoin(page_url, item)
        if allowed_host(absolute, office) and DETAIL_HINT.search(urlparse(absolute).path):
            return absolute

    msg = re.search(r"msg_seq\D+(\d+)", raw, re.I)
    if msg and "dongbu" in (parsed_page.hostname or ""):
        return urljoin(page_url, f"/bbs/bbsMsgDetail.do?bcd=job_offer&msg_seq={msg.group(1)}")
    return ""


def parse_support_page(html: str, page_url: str, office: dict, lookback_days: int):
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    raw_rows = 0
    dated_rows = 0
    page_dates = []
    detail_ids = []

    for table in soup.find_all("table"):
        hs = headers_for_table(table)
        # Reviewed ICE legacy aliases: Bukbu renders the recruitment title
        # as "제 목" (normalized to 제목) and some responses label it 자료명.
        # Do not require a single modern schema; require a known title alias.
        if not hs or not any(
            h in {"제목", "자료명"} or "제목" in h or "공고명" in h
            for h in hs
        ):
            continue
        for tr in table.find_all("tr"):
            tds = tr.find_all("td", recursive=False)
            if not tds:
                continue
            values = row_values(tr, hs)
            anchors = [a for a in tr.find_all("a") if clean(a.get_text(" ", strip=True))]
            candidates = []
            for anchor in anchors:
                detail = exact_detail_from_anchor(page_url, anchor, office)
                title = clean(anchor.get("title") or anchor.get_text(" ", strip=True))
                if detail and len(title) >= 3:
                    candidates.append((len(title), title, detail))

            # Bukbu's list renders the title as plain table text in some responses
            # while the native BD... detail identity lives in a row-level onclick.
            # Keep the source-native identity and use the explicit title column.
            if not candidates and (urlparse(page_url).hostname or "").lower() == "bukbu.ice.go.kr":
                raw_row = " ".join(
                    clean(x)
                    for x in (
                        tr.get("onclick"),
                        tr.get("data-url"),
                        tr.get("data-href"),
                        str(tr),
                    )
                    if x
                )
                title_text = pick(values, "제목", "공고명", "자료명")
                parsed_page = urlparse(page_url)
                q = parse_qs(parsed_page.query)
                bbs = str((q.get("bbs_mst_idx") or [""])[0])

                # Reviewed live Bukbu evidence shows one anchor per data row but
                # not every response exposes the BD identity as visible row text.
                # Inspect the row's native link attributes/call arguments for the
                # source identity; never synthesize an identity from row number.
                legacy = re.search(r"\\b(BD\\d{6,})\\b", raw_row, re.I)
                if not legacy:
                    for anchor in tr.find_all("a"):
                        native = " ".join(
                            clean(x)
                            for x in (
                                anchor.get("href"),
                                anchor.get("onclick"),
                                anchor.get("data-url"),
                                anchor.get("data-href"),
                                anchor.get("data-id"),
                            )
                            if x
                        )
                        legacy = re.search(r"\\b(BD\\d{6,})\\b", native, re.I)
                        if legacy:
                            break
                if legacy and bbs and len(title_text) >= 3:
                    dq = {"bbs_mst_idx": bbs, "data_idx": legacy.group(1).upper()}
                    if q.get("menu_idx"):
                        dq["menu_idx"] = q["menu_idx"][0]
                    detail = urlunparse(
                        (parsed_page.scheme, parsed_page.netloc, "/bbs/data/view.do", "", urlencode(dq), "")
                    )
                    candidates.append((len(title_text), title_text, detail))

            if not candidates:
                continue
            _, title, detail = max(candidates)
            raw_rows += 1
            detail_ids.append(detail)
            registered = date_norm(pick(values, "등록일", "작성일", "작성일시"))
            if not registered:
                all_dates = [date_norm(m.group(0)) for m in DATE_RE.finditer(clean(tr.get_text(" ", strip=True)))]
                plausible = [x for x in all_dates if x and x <= NOW.strftime("%Y/%m/%d")]
                registered = plausible[-1] if plausible else ""
            if registered:
                dated_rows += 1
                page_dates.append(registered)
            if registered and not recent_enough(registered, lookback_days):
                continue
            title = re.sub(r"^NEW\s*", "", title, flags=re.I).strip()
            if not title or EXCLUDE_WORDS.search(title) or not JOB_WORDS.search(title):
                continue
            school = pick(values, "기관명", "학교명", "소속기관") or school_from_title(title) or office["name"]
            apply_end = date_norm(pick(values, "마감일자", "마감일", "접수마감일"))
            row = {
                "id": "ice-support-" + hashlib.sha1(detail.encode("utf-8")).hexdigest()[:20],
                "province": "인천",
                "school": school,
                "title": title,
                "subject": "",
                "region": "",
                "regions": list(office.get("regions") or []),
                "type": guess_type(title),
                "schoolLevel": guess_level(school, title),
                "applyStart": registered,
                "applyEnd": apply_end,
                "workStart": "",
                "workEnd": "",
                "registered": registered,
                "headcount": "",
                "source": office["name"],
                "checkedSources": [office["name"]],
                "sourceType": "교육지원청 개별 게시판",
                "sourceNetwork": "incheon-support",
                "url": detail,
                "boardUrl": page_url,
                "detailLinkResolved": True,
            }
            sid = canonical_source_id(row)
            if sid:
                row["sourceIdentity"] = sid
            if is_support_population_job(row, as_of=NOW):
                rows.append(row)

    text = clean(soup.get_text(" ", strip=True))
    total = None
    for pattern in (
        r"(?:전체|총)\s*(\d[\d,]*)\s*건",
        r"총\s*게시물\s*(\d[\d,]*)\s*개",
        r"전체\s*(\d[\d,]*)\s*건",
    ):
        match = re.search(pattern, text)
        if match:
            total = int(match.group(1).replace(",", ""))
            break
    explicit_empty = bool(re.search(r"전체\s*0\s*건|총\s*0\s*건|등록된\s*(?:게시물|자료)이?\s*없", text))

    return rows, {
        "rawRows": raw_rows,
        "datedRows": dated_rows,
        "pageDates": page_dates,
        "detailIds": detail_ids,
        "totalRows": total,
        "explicitEmpty": explicit_empty,
        "soup": soup,
    }


def query_page(url: str, key: str, page: int) -> str:
    parsed = urlparse(url)
    q = parse_qs(parsed.query, keep_blank_values=True)
    q[key] = [str(page)]
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, urlencode(q, doseq=True), parsed.fragment))


def next_page_url(soup, current_url: str, page: int, office: dict) -> str:
    # Reviewed stable pagination contracts first.
    host = (urlparse(current_url).hostname or "").lower()
    if host == "bukbu.ice.go.kr":
        # The live Bukbu list exposes pageIndex in its canonical list URL.
        return query_page(current_url, "pageIndex", page + 1)
    if host == "dongbu.ice.go.kr":
        return f"https://dongbu.ice.go.kr/bbs/bbsMsgList.do?bcd=job_offer&pgno={page + 1}"

    wanted = str(page + 1)
    for anchor in soup.find_all("a", href=True):
        label = clean(anchor.get_text(" ", strip=True))
        if label != wanted:
            continue
        href = clean(anchor.get("href"))
        if href.lower().startswith(("javascript:", "#")):
            continue
        absolute = urljoin(current_url, href)
        if allowed_host(absolute, office):
            return absolute

    # Some legacy boards expose only a "next" link at the edge of a pager group.
    for anchor in soup.find_all("a", href=True):
        label = clean(anchor.get_text(" ", strip=True)).lower()
        if label not in PAGER_WORDS:
            continue
        href = clean(anchor.get("href"))
        if href.lower().startswith(("javascript:", "#")):
            continue
        absolute = urljoin(current_url, href)
        if allowed_host(absolute, office):
            return absolute
    return ""


def schema_diagnostic(html: str, page_url: str) -> list[dict]:
    """Return bounded structural evidence only; never emit recruitment content."""
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for table in soup.find_all("table")[:8]:
        th = [re.sub(r"\\s+", "", clean(x.get_text(" ", strip=True))) for x in table.find_all("th")]
        rows = []
        for tr in table.find_all("tr")[:3]:
            cells = tr.find_all(["th", "td"], recursive=False)
            rows.append({
                "cellCount": len(cells),
                "tags": [c.name for c in cells],
                "classes": [clean(" ".join(c.get("class") or [])) for c in cells],
                "anchorCount": len(tr.find_all("a")),
                "anchorShapes": [
                    {
                        "href": clean(a.get("href"))[:160],
                        "onclick": clean(a.get("onclick"))[:160],
                        "dataId": clean(a.get("data-id"))[:80],
                        "attrs": {
                            str(k): clean(v if isinstance(v, str) else " ".join(v))[:160]
                            for k, v in a.attrs.items()
                            if str(k).lower() not in {"class", "style", "title"}
                        },
                        "parentAttrs": {
                            str(k): clean(v if isinstance(v, str) else " ".join(v))[:160]
                            for k, v in (a.parent.attrs if a.parent else {}).items()
                            if str(k).lower() not in {"class", "style"}
                        },
                    }
                    for a in tr.find_all("a")[:2]
                ],
                "hasBDIdentity": bool(re.search(r"\\bBD\\d{6,}\\b", str(tr), re.I)),
            })
        out.append({"page": page_url, "headers": th[:12], "rows": rows})
    return out


def crawl_board(board_url: str, office: dict, lookback_days: int, max_pages: int):
    all_rows = []
    seen_ids = set()
    seen_page_signatures = set()
    pages_scanned = 0
    raw_rows_total = 0
    access_error = ""
    pagination_repeated = False
    crossed_lookback = False
    natural_end = False
    explicit_empty = False
    total_rows_hint = None
    current = board_url
    consecutive_old_pages = 0
    diagnostic = []

    for page in range(1, max_pages + 1):
        try:
            response = fetch(current)
        except Exception as exc:
            access_error = f"{type(exc).__name__}: {str(exc)[:160]}"
            break
        if not allowed_host(response.url, office):
            access_error = f"redirected to unapproved host: {response.url}"
            break

        parsed_rows, meta = parse_support_page(response.text, response.url, office, lookback_days)
        if page == 1 and (urlparse(response.url).hostname or "").lower() == "bukbu.ice.go.kr":
            diagnostic = schema_diagnostic(response.text, response.url)
        pages_scanned += 1
        raw_rows_total += int(meta.get("rawRows") or 0)
        explicit_empty = explicit_empty or bool(meta.get("explicitEmpty"))
        if meta.get("totalRows") is not None:
            total_rows_hint = int(meta["totalRows"])

        signature = tuple(meta.get("detailIds") or [])
        if signature and signature in seen_page_signatures:
            pagination_repeated = True
            break
        if signature:
            seen_page_signatures.add(signature)

        for row in parsed_rows:
            sid = canonical_source_id(row) or row.get("id", "")
            if sid and sid not in seen_ids:
                seen_ids.add(sid)
                all_rows.append(row)

        dates = [x for x in meta.get("pageDates", []) if x]
        if dates and all(definitely_old(x, lookback_days) for x in dates):
            consecutive_old_pages += 1
        else:
            consecutive_old_pages = 0
        if consecutive_old_pages >= 2:
            crossed_lookback = True
            break

        nxt = next_page_url(meta["soup"], response.url, page, office)
        if not nxt:
            if explicit_empty or (total_rows_hint is not None and raw_rows_total >= total_rows_hint):
                natural_end = True
            elif int(meta.get("rawRows") or 0) == 0 and pages_scanned > 1:
                natural_end = True
            break
        current = nxt
        time.sleep(0.05)
    else:
        access_error = f"emergency page ceiling reached: {max_pages}"

    complete = bool(
        not access_error
        and not pagination_repeated
        and (crossed_lookback or natural_end or explicit_empty)
    )
    return all_rows, {
        "url": board_url,
        "pagesScanned": pages_scanned,
        "rawRows": raw_rows_total,
        "recentRows": len(all_rows),
        "coverageComplete": complete,
        "accessError": access_error,
        "paginationRepeated": pagination_repeated,
        "crossedLookback": crossed_lookback,
        "naturalEnd": natural_end,
        "explicitEmpty": explicit_empty,
        "totalRowsHint": total_rows_hint,
        "latestRegistered": max((x.get("registered", "") for x in all_rows), default=""),
        "schemaDiagnostic": diagnostic,
    }


def crawl_office(office: dict, lookback_days: int, max_pages: int):
    candidates, discovery = discover_support_boards(office)
    attempts = []
    for board in candidates:
        rows, meta = crawl_board(board, office, lookback_days, max_pages)
        attempts.append((rows, meta))
        if meta.get("coverageComplete"):
            return rows, {
                "name": office["name"],
                "url": office.get("url", ""),
                "boards": [board],
                "count": len(rows),
                "rawRows": int(meta.get("rawRows") or 0),
                "pagesScanned": int(meta.get("pagesScanned") or 0),
                "ok": True,
                "state": "complete" if rows else "empty",
                "message": f"최근 {lookback_days}일 범위 공식 채용게시판 완전수집",
                "coverageComplete": True,
                "boardHealth": [meta],
                "discoveryEvidence": discovery,
            }

    metas = [meta for _rows, meta in attempts]
    reason = "공식 채용 게시판을 발견하지 못함" if not candidates else "공식 채용 게시판 완전수집을 증명하지 못함"
    return [], {
        "name": office["name"],
        "url": office.get("url", ""),
        "boards": candidates,
        "count": 0,
        "rawRows": sum(int(x.get("rawRows") or 0) for x in metas),
        "pagesScanned": sum(int(x.get("pagesScanned") or 0) for x in metas),
        "ok": False,
        "state": "error",
        "message": reason,
        "coverageComplete": False,
        "boardHealth": metas,
        "discoveryEvidence": discovery,
    }


def crawl_all_support_offices(lookback_days: int = 90, max_pages: int = 500):
    registry = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    offices = ((registry.get("incheon") or {}).get("supportOffices") or [])
    if len(offices) != 5:
        raise RuntimeError(f"Incheon support-office registry must contain exactly 5 offices, found {len(offices)}")

    results = []
    all_rows = []
    for office in offices:
        rows, status = crawl_office(office, lookback_days, max_pages)
        results.append({"office": office, "rows": rows, "status": status})
        all_rows.extend(rows)
    return results, all_rows


def fingerprint(job: dict) -> str:
    return "|".join(
        (
            str(job.get("province") or ""),
            norm_key(job.get("school") or ""),
            norm_key(job.get("title") or ""),
            date_norm(job.get("registered") or ""),
        )
    )


def merge_support_rows(payload: dict, office_results: list[dict]) -> tuple[int, int]:
    jobs = list(payload.get("jobs") or [])
    support_names = {item["office"]["name"] for item in office_results}

    # Replace prior support-office observations from this collector; central/private rows remain.
    jobs = [
        job for job in jobs
        if not (
            job.get("province") == "인천"
            and (job.get("source") in support_names or job.get("sourceNetwork") == "incheon-support")
        )
    ]

    by_fp = {}
    for job in jobs:
        fp = fingerprint(job)
        if fp and fp.count("|") == 3:
            by_fp.setdefault(fp, job)

    added = 0
    collapsed = 0
    for result in office_results:
        for row in result["rows"]:
            sid = canonical_source_id(row)
            fp = fingerprint(row)
            existing = by_fp.get(fp)
            if existing is not None:
                identities = list(existing.get("sourceIdentities") or [])
                primary = canonical_source_id(existing)
                if primary and primary not in identities:
                    identities.append(primary)
                if sid and sid not in identities:
                    identities.append(sid)
                existing["sourceIdentities"] = identities

                checked = list(existing.get("checkedSources") or [existing.get("source", "")])
                if row["source"] not in checked:
                    checked.append(row["source"])
                existing["checkedSources"] = [x for x in checked if x]

                occurrences = list(existing.get("sourceOccurrences") or [])
                occurrence = {
                    "source": row.get("source"),
                    "sourceIdentity": sid,
                    "url": row.get("url"),
                    "registered": row.get("registered"),
                }
                if occurrence not in occurrences:
                    occurrences.append(occurrence)
                existing["sourceOccurrences"] = occurrences
                collapsed += 1
                continue

            if sid:
                row["sourceIdentity"] = sid
                row["sourceIdentities"] = [sid]
            jobs.append(row)
            by_fp[fp] = row
            added += 1

    jobs.sort(key=lambda j: (j.get("registered", ""), j.get("applyEnd", "")), reverse=True)
    payload["jobs"] = jobs
    return added, collapsed


def apply_runtime_status(payload: dict, office_results: list[dict], lookback_days: int):
    statuses = [item["status"] for item in office_results]
    payload.setdefault("sources", {}).setdefault("incheon", {})["supportOffices"] = statuses
    comp = payload.setdefault("supportCompleteness", {})
    old_warnings = [
        x for x in (comp.get("warnings") or [])
        if x not in {status.get("name") for status in statuses}
    ]
    warnings = [status["name"] for status in statuses if not (status.get("ok") and status.get("coverageComplete"))]
    comp.update(
        {
            "lookbackDays": lookback_days,
            "incheonTotal": len(statuses),
            "incheonComplete": sum(1 for status in statuses if status.get("ok") and status.get("coverageComplete")),
            "warnings": old_warnings + warnings,
        }
    )


def write_report(office_results: list[dict], added: int, collapsed: int, lookback_days: int, merged: bool):
    statuses = [item["status"] for item in office_results]
    report = {
        "generatedAt": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST"),
        "lookbackDays": lookback_days,
        "officeCount": len(statuses),
        "completeOffices": sum(1 for x in statuses if x.get("coverageComplete")),
        "merged": merged,
        "newlyAddedJobs": added,
        "crossSourceDuplicatesCollapsed": collapsed,
        "offices": statuses,
        "sample": [
            {
                "source": row.get("source"),
                "sourceIdentity": canonical_source_id(row),
                "school": row.get("school"),
                "title": row.get("title"),
                "registered": row.get("registered"),
                "url": row.get("url"),
            }
            for item in office_results
            for row in item["rows"][:3]
        ],
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lookback-days", type=int, default=90)
    parser.add_argument("--max-pages", type=int, default=500)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    results, _rows = crawl_all_support_offices(args.lookback_days, args.max_pages)
    incomplete = [item["status"]["name"] for item in results if not item["status"].get("coverageComplete")]
    if incomplete:
        report = write_report(results, 0, 0, args.lookback_days, merged=False)
        raise SystemExit(
            "Incheon support-office coverage incomplete: "
            + ", ".join(incomplete)
            + " | "
            + json.dumps(report, ensure_ascii=False)[:2500]
        )

    if args.check_only:
        report = write_report(results, 0, 0, args.lookback_days, merged=False)
        print(json.dumps({"state": "ok", "offices": report["completeOffices"]}, ensure_ascii=False))
        return 0

    payload = json.loads(JOBS_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        raise SystemExit("jobs.json is not a valid publication payload")
    added, collapsed = merge_support_rows(payload, results)
    apply_runtime_status(payload, results, args.lookback_days)
    JOBS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report = write_report(results, added, collapsed, args.lookback_days, merged=True)
    print(
        json.dumps(
            {
                "state": "ok",
                "completeOffices": report["completeOffices"],
                "newlyAddedJobs": added,
                "crossSourceDuplicatesCollapsed": collapsed,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
