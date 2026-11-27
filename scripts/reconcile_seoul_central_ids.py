#!/usr/bin/env python3
"""Reconcile live-proven Seoul central source-native IDs against staged Regional jobs.

Fail closed when independent full-list evidence and the staged dataset disagree,
unless a second verified first-party crawl can recover *exact* native IDs.
Never bypass publication gates, change source registry, or touch production files.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from stable_source_identity import canonical_source_id

ROOT = Path(__file__).resolve().parents[1]
KST = timezone(timedelta(hours=9))
EXPECTED_HOST = "work.sen.go.kr"
CENTRAL_SOURCE = "서울교육일자리포털"
ID_RE = re.compile(r"^[1-9]\d{3,12}$")


def required_source_ids(proof: dict) -> set[str]:
    if proof.get("complete") is not True:
        raise ValueError("independent central source pagination incomplete")
    sources = [s for s in proof.get("sources", [])
               if s.get("province") == "서울" and s.get("name") == CENTRAL_SOURCE]
    if len(sources) != 1:
        raise ValueError("expected exactly one independent Seoul central source")
    src = sources[0]
    if (src.get("complete") is not True or src.get("accessError") or
            src.get("parseError") or src.get("paginationRepeated") or src.get("capHit")):
        raise ValueError("independent Seoul native-list traversal not trustworthy")
    raw = src.get("sourceNativeRecruitmentIds")
    if not isinstance(raw, list) or not raw:
        raise ValueError("independent Seoul source IDs unavailable; no count-only pass")
    ids = [str(x) for x in raw]
    if (any(not ID_RE.fullmatch(x) for x in ids) or len(set(ids)) != len(ids) or
            len(ids) != int(src.get("stableIdCount") or 0)):
        raise ValueError("Seoul source-ID list does not match independently counted IDs")
    return set(ids)


def native_id(job: dict) -> str:
    if job.get("province") != "서울" or job.get("sourceType") != "통합게시판":
        return ""
    url = str(job.get("url") or "")
    parsed = urlparse(url)
    if (parsed.scheme != "https" or (parsed.hostname or "").lower() != EXPECTED_HOST or
            parsed.path != "/work/search/recInfo/BD_selectRecDetail.do"):
        return ""
    ids = parse_qs(parsed.query).get("q_rcrtSn") or []
    if len(ids) != 1 or not ID_RE.fullmatch(ids[0]):
        return ""
    wanted = "seoul-central:" + ids[0]
    return ids[0] if canonical_source_id(job) == wanted else ""


def reconcile(candidate: dict, proof: dict, fetch_rows):
    """Pure reconciliation; caller writes jobs.json only after all checks pass."""
    required = required_source_ids(proof)
    jobs = candidate.get("jobs")
    if not isinstance(jobs, list):
        raise ValueError("regional jobs list not available")
    have = {sid for j in jobs if isinstance(j, dict) if (sid := native_id(j))}
    missing = required - have
    additions = []
    if missing:
        # The primary collector does a real first-party list crawl, not a
        # guessed detail URL read or a cached historical snapshot.
        fresh = fetch_rows()
        if not isinstance(fresh, list):
            raise ValueError("live Seoul central re-crawl returned no usable list")
        by_id = {}
        for row in fresh:
            if not isinstance(row, dict):
                continue
            sid = native_id(row)
            if sid and sid in missing:
                if sid in by_id:
                    raise ValueError("duplicate native ID in second Seoul central traversal")
                by_id[sid] = row
        unresolved = missing - set(by_id)
        if unresolved:
            raise ValueError(
                "independently verified Seoul central native IDs unrecovered: " +
                ",".join(sorted(unresolved)[:12]))
        additions = [by_id[sid] for sid in sorted(missing)]
    result = dict(candidate)
    result["jobs"] = jobs + additions
    actual = {sid for j in result["jobs"] if isinstance(j, dict) if (sid := native_id(j))}
    unresolved = required - actual
    if unresolved:
        raise ValueError("Seoul source ID reconciliation still incomplete")
    result["seoulCentralIdReconciliation"] = {
        "verified": True,
        "expectedSourceIds": len(required),
        "previousMissing": len(missing),
        "recoveredNow": len(additions),
        "missingAfter": 0,
        "checkedAt": datetime.now(KST).isoformat(timespec="seconds"),
        "policy": "source-native-independent-list-fail-closed-v1",
    }
    # The primary source status must agree with source-native rows after recovery.
    group = (result.get("sources") or {}).get("seoul") or {}
    status = group.get("central") or {}
    if isinstance(status, dict):
        status = dict(status)
        status["count"] = len(actual)
        group = dict(group)
        group["central"] = status
        sources = dict(result["sources"])
        sources["seoul"] = group
        result["sources"] = sources
    return result


def main():
    from scrape_jobs import scrape_seoul_central

    input_path = ROOT / "jobs.json"
    proof_path = ROOT / "central_pagination_report.json"
    candidate = json.loads(input_path.read_text(encoding="utf-8"))
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    verified = reconcile(candidate, proof, scrape_seoul_central)
    # The isolated official workflow restores jobs.json before publication;
    # only the finalized independently verified Regional files are committed.
    input_path.write_text(json.dumps(verified, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(verified["seoulCentralIdReconciliation"], ensure_ascii=False))


if __name__ == "__main__":
    main()
