#!/usr/bin/env python3
"""Repair carried Seoul SEN rows only from their exact official detail fields."""
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from stable_source_identity import canonical_source_id

ROOT = Path(__file__).resolve().parents[1]
JOBS_PATH = ROOT / "jobs.json"
REPORT_PATH = ROOT / "seoul_support_metadata_report.json"
LEDGER_PATH = ROOT / "source_id_ledger.json"
KST = timezone(timedelta(hours=9))
TODAY = datetime.now(KST).date()
DATE_RE = re.compile(r"(20\d{2})[./-](\d{1,2})[./-](\d{1,2})")
MAX_CANDIDATES = 40


def norm(value):
    return re.sub(r"\s+", "", str(value or ""))


def date(value):
    m = DATE_RE.search(str(value or ""))
    if not m:
        return ""
    try:
        return datetime(int(m[1]), int(m[2]), int(m[3])).strftime("%Y/%m/%d")
    except ValueError:
        return ""


def fields(html):
    result = {}
    soup = BeautifulSoup(html, "html.parser")
    for tr in soup.find_all("tr"):
        for th in tr.find_all("th"):
            td = th.find_next_sibling("td")
            if td:
                result[th.get_text(" ", strip=True)] = td.get_text(" ", strip=True)
    return result


def single_page_ids(html):
    """Require the board's declared total to equal all distinct visible detail IDs."""
    soup = BeautifulSoup(html, "html.parser")
    match = re.search(r"Total\s*:\s*(\d+)\s*개\s*\(Page\s*1\s*/\s*(\d+)\s*\)", soup.get_text(" ", strip=True), re.I)
    if not match or int(match[2]) != 1:
        return None
    ids = set(re.findall(r"fncDetailView\s*\(\s*['\"]?(\d+)", html, re.I))
    return ids if ids and len(ids) == int(match[1]) else None


def complete_board_ids(session, board):
    """Two transport methods must independently agree on a complete one-page list."""
    try:
        get_response = session.get(board, params={"pageIndex": 1}, timeout=12)
        post_response = session.post(board, data={"pageIndex": "1", "searchPartPosition": "", "searchCondition": "lesson", "searchKeyword": ""}, timeout=12)
        get_response.raise_for_status()
        post_response.raise_for_status()
        first = single_page_ids(get_response.text)
        second = single_page_ids(post_response.text)
        return first if first and first == second else None
    except requests.RequestException:
        return None


def prove_absent_from_board(session, board, seq):
    ids = complete_board_ids(session, board)
    return ids is not None and seq not in ids


def needs_repair(job):
    if job.get("province") != "서울" or job.get("sourceType") != "교육지원청 개별 게시판":
        return False
    seq = str((job.get("openParams") or {}).get("job_seq") or "")
    if not seq.isdecimal() or job.get("openMethod") != "POST":
        return False
    deadline = date(job.get("applyEnd"))
    if deadline and deadline < TODAY.strftime("%Y/%m/%d"):
        return False
    return not date(job.get("registered")) or norm(job.get("title")) in {
        norm(job.get("school")), norm(job.get("source"))
    }


def repair(job, session):
    seq = str(job["openParams"]["job_seq"])
    url = str(job.get("openUrl") or "")
    board = str(job.get("boardUrl") or "")
    if not url.startswith("https://") or urlparse(url).hostname != urlparse(board).hostname or not url.endswith("/FUS/JO/JOV11.do"):
        return "invalid-exact-detail-url"
    try:
        response = session.post(url, data={"job_seq": seq}, headers={"Referer": board}, timeout=12)
        response.raise_for_status()
        if not response.encoding or response.encoding.lower() == "iso-8859-1":
            response.encoding = response.apparent_encoding or "utf-8"
    except requests.RequestException:
        return "detail-unavailable"
    values = fields(response.text)
    registered = date(values.get("등록일자"))
    deadline = date(values.get("마감일자"))
    school = str(values.get("기관명") or "").strip()
    subject = str(values.get("분야(과목)") or "").strip()
    if not registered or not deadline or not school or not subject:
        return "detail-empty-or-incomplete"
    if registered > TODAY.strftime("%Y/%m/%d") or registered > deadline:
        return "detail-date-conflict"
    if date(job.get("applyEnd")) and date(job["applyEnd"]) != deadline:
        return "detail-deadline-conflict"
    old_school = norm(job.get("school"))
    if old_school and old_school != norm(school) and old_school != norm(job.get("source")):
        return "detail-institution-conflict"
    # Both legacy collectors used to copy the posting date into application start.
    # The detail has no verified application-start field in this repair path.
    if (str(job.get("id") or "").startswith(("sen-complete-", "sen-office-"))
            and date(job.get("applyStart")) == date(job.get("registered"))
            and job.get("periodStatus") != "parsed"):
        job["applyStart"] = ""
    job["registered"] = registered
    job["school"] = school
    job["applyEnd"] = deadline
    if norm(job.get("title")) in {old_school, norm(job.get("source"))}:
        job["title"] = subject
    if not job.get("subject"):
        job["subject"] = subject
    # An application period is not implied by registration; retain any known value.
    return "repaired"


def main():
    payload = json.loads(JOBS_PATH.read_text(encoding="utf-8"))
    jobs = payload.get("jobs", [])
    candidates = [job for job in jobs if needs_repair(job)]
    ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8")) if LEDGER_PATH.exists() else {}
    ledger_entries = ledger.get("entries", {}) if isinstance(ledger, dict) else {}
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; metro-edujob-metadata-repair/1.0)", "Accept-Language": "ko-KR,ko;q=0.9"})
    outcomes = []
    removed_ids = set()
    removed_sids = set()
    board_proofs = {}
    for job in candidates[:MAX_CANDIDATES]:
        original_title = job.get("title")
        result = repair(job, session)
        seq = str(job["openParams"]["job_seq"])
        sid = canonical_source_id(job)
        ledger_entry = ledger_entries.get(sid, {}) if sid else {}
        if result == "detail-empty-or-incomplete" and ledger_entry.get("presentInLatestOfficialScan") is False:
            proof_key = job.get("boardUrl")
            if proof_key not in board_proofs:
                board_proofs[proof_key] = complete_board_ids(session, proof_key)
            if board_proofs[proof_key] is not None and seq not in board_proofs[proof_key]:
                result = "removed-proven-absent"
                removed_ids.add(job.get("id"))
                removed_sids.add(sid)
        outcomes.append({"id": job.get("id"), "result": result,
                         "originalTitle": original_title,
                         "titleSource": "official-detail-분야(과목)" if job.get("title") != original_title else "unchanged",
                         "registrationSource": "official-detail-등록일자" if result == "repaired" else "unchanged"})
    if removed_ids:
        payload["jobs"] = [job for job in jobs if canonical_source_id(job) not in removed_sids]
    report = {"checkedAt": datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"), "candidates": len(candidates),
              "repaired": sum(x["result"] == "repaired" for x in outcomes), "outcomes": outcomes,
              "removedProvenAbsent": len(jobs) - len(payload["jobs"]),
              "capped": len(candidates) > MAX_CANDIDATES}
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if report["repaired"] or removed_ids:
        JOBS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("SEOUL SUPPORT METADATA", report["candidates"], report["repaired"], report["capped"])


if __name__ == "__main__":
    main()
