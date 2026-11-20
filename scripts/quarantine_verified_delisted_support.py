#!/usr/bin/env python3
"""Quarantine *proven* delisted and dead Gyeonggi support URLs before publication.

A candidate may be removed from the staged, unpublished jobs.json only if:
1. the existing independent detail verifier actually saw HTTP 400/404/410;
2. a new complete official 90-day crawl of the source's canonical board proves
   the exact bbsId+nttSn is ABSENT, with no access/pagination errors;
3. a second normal exact-URL request confirms the detail is still HTTP 400/404/410.

All other failures (including 403, 429, 5xx, incomplete source, or a still-listed ID)
retain the original job and the downstream fail-closed verifier. Never mutate the
persisted last-known-good Regional, Unified, or Incheon.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
import complete_support_coverage as coverage
import verify_jobs

ROOT = Path(__file__).resolve().parents[1]
KST = timezone(timedelta(hours=9))
DELETED_STATUSES = frozenset((400, 404, 410))
MAX_SUSPECTS = 8
MAX_OFFICES = 3


def canonical_board_id(url: str, board: str) -> str:
    """Return only the official board's strongly bound source-native posting ID."""
    try:
        p = urlparse(str(url or ""))
        b = urlparse(board)
        pq = parse_qs(p.query)
        bq = parse_qs(b.query)
        if (p.scheme != "https" or p.hostname != b.hostname or
                p.path != b.path.replace("selectNttList.do", "selectNttInfo.do") or
                (pq.get("bbsId") or [""])[0] != (bq.get("bbsId") or [""])[0] or
                (pq.get("mi") or [""])[0] != (bq.get("mi") or [""])[0]):
            return ""
        ids = pq.get("nttSn") or []
        return ids[0] if len(ids) == 1 and re.fullmatch(r"[1-9]\d{4,11}", ids[0]) else ""
    except (TypeError, ValueError):
        return ""


def official_board_for(row: dict, registry: dict):
    if row.get("province") != "경기" or row.get("sourceType") != "교육지원청 개별 게시판":
        return None
    matches = [s for s in registry.get("gyeonggi", {}).get("supportOffices", [])
               if s.get("name") == row.get("source")]
    if len(matches) != 1:
        return None
    src = matches[0]
    boards = src.get("boardUrls") or []
    # A one-board identity is the only safe minimal scope. Offices with multiple
    # categories/menus require a different multi-board population proof.
    if len(boards) != 1:
        return None
    if not canonical_board_id(row.get("url", ""), boards[0]):
        return None
    return src, boards[0]


def suspect_rows(jobs, findings, registry):
    by_url = {str(j.get("url") or ""): j for j in jobs if isinstance(j, dict)}
    out = []
    seen = set()
    for f in findings:
        if (f.get("hard") is not True or type(f.get("status")) is not int or
                f["status"] not in DELETED_STATUSES):
            continue
        url = str(f.get("url") or "")
        row = by_url.get(url)
        if row is None or url in seen:
            continue
        board_info = official_board_for(row, registry)
        if not board_info:
            continue
        seen.add(url)
        out.append((row, board_info[0], board_info[1]))
    if len(out) > MAX_SUSPECTS or len({s["name"] for _, s, _ in out}) > MAX_OFFICES:
        raise ValueError("too many broken support IDs to quarantine without manual audit")
    return out


def confirmed_unavailable(session, url: str, board: str) -> bool:
    # Only ordinary same-host GET; no authentication, anti-bot bypass, or invented URL.
    try:
        r = session.get(url, timeout=(6, 15), allow_redirects=True)
        b = urlparse(board)
        final = urlparse(r.url)
        return (r.status_code in DELETED_STATUSES and
                final.scheme == "https" and final.hostname == b.hostname and
                final.path == b.path.replace("selectNttList.do", "selectNttInfo.do"))
    except requests.RequestException:
        return False


def quarantine(jobs, findings, registry, scan_board, probe):
    suspects = suspect_rows(jobs, findings, registry)
    if not suspects:
        return list(jobs), {"checkedDeadLinks": 0, "quarantined": 0, "ids": []}
    verified = {}
    delisted = set()
    for row, source, board in suspects:
        key = (source["name"], board)
        if key not in verified:
            full_rows, health = scan_board(board, source)
            if not (health.get("coverageComplete") is True and
                    not health.get("accessError") and not health.get("paginationRepeated") and
                    not health.get("paginationCounterMismatch") and
                    (health.get("crossedLookback") or health.get("naturalEnd"))):
                raise ValueError("official 90-day board proof incomplete: " + source["name"])
            # Strong native ID only: title/date similarity is never evidence.
            verified[key] = {
                canonical_board_id(j.get("url", ""), board)
                for j in full_rows if isinstance(j, dict)
            } - {""}
            if not verified[key]:
                raise ValueError("official 90-day board has no strong native IDs")
        sid = canonical_board_id(row["url"], board)
        if sid not in verified[key] and probe(row["url"], board):
            delisted.add((source["name"], board, sid))
    removal_urls = {
        row["url"] for row, src, board in suspects
        if (src["name"], board, canonical_board_id(row["url"], board)) in delisted
    }
    safe = [row for row in jobs if str(row.get("url") or "") not in removal_urls]
    report = {
        "checkedDeadLinks": len(suspects),
        "quarantined": len(jobs) - len(safe),
        "ids": sorted(sid for _, _, sid in delisted),
        "policy": "complete-live-90d-absent-and-confirmed-http400-404-410-v1",
    }
    return safe, report



def proactively_quarantine_office(jobs, registry, office, scan_board, probe):
    """Source-wide native-ID verification is independent of the 50-link sample.

    Only the currently P0-affected one-board Kimpo source is enabled in the
    production call below. The full source-list proof must succeed before
    inspecting any missing candidates, and exact HTTP 400/404/410 must recur.
    """
    sources = [x for x in registry.get("gyeonggi", {}).get("supportOffices", [])
               if x.get("name") == office]
    if len(sources) != 1 or len(sources[0].get("boardUrls") or []) != 1:
        raise ValueError("proactive source requires exactly one canonical official board")
    src = sources[0]
    board = src["boardUrls"][0]
    candidates = [j for j in jobs if isinstance(j, dict) and
                  j.get("source") == office and
                  canonical_board_id(j.get("url", ""), board)]
    if not candidates:
        return list(jobs), {"checkedDeadLinks": 0, "quarantined": 0, "ids": [],
                            "sourceScanned": False}
    full_rows, health = scan_board(board, src)
    if not (health.get("coverageComplete") is True and
            not health.get("accessError") and not health.get("paginationRepeated") and
            not health.get("paginationCounterMismatch") and
            (health.get("crossedLookback") or health.get("naturalEnd"))):
        raise ValueError("proactive full 90-day official source proof incomplete")
    actual = {canonical_board_id(j.get("url", ""), board)
              for j in full_rows if isinstance(j, dict)} - {""}
    if not actual:
        raise ValueError("proactive full source scan produced no strong native IDs")
    missing = [j for j in candidates if canonical_board_id(j["url"], board) not in actual]
    if len(missing) > MAX_SUSPECTS:
        raise ValueError("too many missing Kimpo posting IDs; refuse bulk quarantine")
    removed_urls = set()
    native_ids = set()
    for j in missing:
        if probe(j["url"], board):
            removed_urls.add(j["url"])
            native_ids.add(canonical_board_id(j["url"], board))
    result = [j for j in jobs if str(j.get("url") or "") not in removed_urls]
    return result, {"checkedDeadLinks": len(missing), "quarantined": len(jobs) - len(result),
                    "ids": sorted(native_ids), "sourceScanned": True}

def main():
    path = ROOT / "jobs.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    jobs = data.get("jobs") or []
    _, findings = verify_jobs.verify_links(jobs)
    source = coverage.SOURCES
    session = verify_jobs.build_session()
    live_probe = lambda url, board: confirmed_unavailable(session, url, board)
    # Kimpo's broken 1148220 was one of 50 verified links on the failed run,
    # but could fall OUT of the sample after a new posting arrives. Prove all
    # exact Kimpo IDs proactively against the full authentic board population.
    after_proactive, proactive = proactively_quarantine_office(
        jobs, source, "김포교육지원청", coverage.gyeonggi_board, live_probe
    )
    result, sampled = quarantine(
        after_proactive, findings, source, coverage.gyeonggi_board, live_probe
    )
    report = {
        "checkedDeadLinks": proactive["checkedDeadLinks"] + sampled["checkedDeadLinks"],
        "quarantined": proactive["quarantined"] + sampled["quarantined"],
        "ids": sorted(set(proactive["ids"] + sampled["ids"])),
        "proactiveKimpoFullScan": proactive["sourceScanned"],
        "policy": "complete-live-90d-absent-and-confirmed-http400-404-410-v1",
    }
    if report["quarantined"]:
        # The write is to the private WORKSPACE ONLY; public publication remains
        # guarded by all existing 90-day, exact URL and transaction checks.
        data["jobs"] = result
        data["verifiedDelistedSupportQuarantine"] = {
            **report, "checkedAt": datetime.now(KST).isoformat(timespec="seconds"),
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("VERIFIED_DELISTED_SUPPORT_QUARANTINE", json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
