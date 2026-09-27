#!/usr/bin/env python3
"""Repair carried Seoul SEN rows only from their exact official detail fields."""
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
JOBS_PATH = ROOT / "jobs.json"
REPORT_PATH = ROOT / "seoul_support_metadata_report.json"
KST = timezone(timedelta(hours=9))
TODAY = datetime.now(KST).date()
DATE_RE = re.compile(r"(20\d{2})[./-](\d{1,2})[./-](\d{1,2})")


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
        response = session.post(url, data={"job_seq": seq}, headers={"Referer": board}, timeout=18)
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
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; metro-edujob-metadata-repair/1.0)", "Accept-Language": "ko-KR,ko;q=0.9"})
    outcomes = []
    for job in candidates[:200]:
        outcomes.append({"id": job.get("id"), "result": repair(job, session)})
    report = {"checkedAt": datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"), "candidates": len(candidates),
              "repaired": sum(x["result"] == "repaired" for x in outcomes), "outcomes": outcomes,
              "capped": len(candidates) > 200}
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if report["repaired"]:
        JOBS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("SEOUL SUPPORT METADATA", report["candidates"], report["repaired"], report["capped"])


if __name__ == "__main__":
    main()
