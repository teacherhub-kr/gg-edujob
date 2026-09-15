#!/usr/bin/env python3
"""Evidence-based comparison audit for the historical support-office snapshot."""
from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from stable_source_identity import canonical_source_id
from support_population_contract import contract_metadata, is_support_population_job

HIST = "432aaa232106e206d92ec6b971fd5dec979ab363"
OUT = Path("support_71_diff_audit.json")
UA = "gg-edujob/support-diff-audit"
KST = timezone(timedelta(hours=9))

STRONG_ID_MOVE = "strong-ID 이동"
CANONICAL_URL_MOVE = "canonical URL 이동"
OFFICIAL_ENDED = "공식 페이지 종료·삭제"
EXPIRED = "기간 만료"
ACTUAL_MISSING = "실제 활성 누락"
UNVERIFIABLE = "확인 불가"

DELETION_MARKERS = (
    "존재하지 않는 게시물", "존재하지 않는 글", "삭제된 게시물", "삭제된 글",
    "게시물이 삭제", "요청하신 페이지를 찾을 수 없습니다",
)


def git_json(ref, path):
    return json.loads(
        subprocess.check_output(
            ["git", "show", f"{ref}:{path}"], text=True, encoding="utf-8"
        )
    )


def as_jobs(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("jobs", "data", "items"):
            if isinstance(payload.get(key), list):
                return payload[key]
    raise ValueError(f"unsupported jobs.json shape: {type(payload).__name__}")


def is_support(job, as_of):
    return is_support_population_job(job, as_of=as_of)


def identity(job):
    return canonical_source_id(job)


def title(job):
    return " ".join(str(job.get("title") or "").split())


def url(job):
    return str(job.get("url") or job.get("detailUrl") or job.get("originalUrl") or "").strip()


def parse_date(value):
    token = str(value or "").strip()[:10].replace("/", "-").replace(".", "-")
    try:
        return date.fromisoformat(token)
    except ValueError:
        return None


def fetch(url_):
    """Return only the official-page evidence needed by classification."""
    if not url_:
        return {"status": "error", "probe": "no-url"}
    request = Request(url_, headers={"User-Agent": UA})
    try:
        with urlopen(request, timeout=15) as response:
            body = response.read(1_000_000).decode(response.headers.get_content_charset() or "utf-8", "replace")
            return {"status": "ok", "http": response.status, "finalUrl": response.geturl(), "body": " ".join(body.split())}
    except HTTPError as exc:
        return {"status": "ok", "http": exc.code, "finalUrl": exc.geturl(), "body": ""}
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        return {"status": "error", "probe": f"error:{type(exc).__name__}"}


def build(rows):
    by_id = {}
    collisions = 0
    failures = []
    for job in rows:
        sid = identity(job)
        if not sid:
            failures.append(job)
            continue
        if sid in by_id:
            collisions += 1
        else:
            by_id[sid] = job
    return by_id, collisions, failures


def row(old, classification, **evidence):
    result = {"oldId": identity(old), "classification": classification, "title": title(old), "url": url(old)}
    result.update(evidence)
    return result


def redirected_identity(old, final_url):
    candidate = dict(old)
    candidate["url"] = final_url
    candidate.pop("openUrl", None)
    candidate.pop("openParams", None)
    return identity(candidate)


def classify(old, current, *, as_of, probe=fetch):
    """Classify with strong identity and official-page evidence only."""
    oid = identity(old)
    if not oid:
        return row(old, UNVERIFIABLE, reason="strong identity parse failure")

    same = current.get(oid)
    if same is not None:
        return row(old, STRONG_ID_MOVE, newId=oid, newUrl=url(same), newTitle=title(same), evidence="same canonical strong identity")

    end = parse_date(old.get("applyEnd") or old.get("deadline"))
    if end is not None and end < as_of:
        return row(old, EXPIRED, applyEnd=end.isoformat(), evidence="deadline before audit date")

    evidence = probe(url(old))
    if evidence.get("status") != "ok":
        return row(old, UNVERIFIABLE, probe=evidence.get("probe", "probe-failed"))

    http = int(evidence.get("http") or 0)
    body = str(evidence.get("body") or "")
    final_url = str(evidence.get("finalUrl") or url(old))
    if http in (404, 410) or any(marker in body for marker in DELETION_MARKERS):
        return row(old, OFFICIAL_ENDED, http=http, finalUrl=final_url)

    final_id = redirected_identity(old, final_url)
    if final_id and final_id != oid and final_id in current:
        moved = current[final_id]
        return row(old, CANONICAL_URL_MOVE, newId=final_id, newUrl=url(moved), newTitle=title(moved), http=http, finalUrl=final_url, evidence="official redirect resolves to current canonical detail identity")

    if 200 <= http < 400 and end is not None and end >= as_of:
        return row(old, ACTUAL_MISSING, http=http, finalUrl=final_url, applyEnd=end.isoformat(), evidence="official detail is reachable before its deadline")

    reason = "reachable page has no valid active deadline" if 200 <= http < 400 else "ambiguous official response"
    return row(old, UNVERIFIABLE, http=http, finalUrl=final_url, reason=reason)


def failure_row(job, snapshot):
    return row(job, UNVERIFIABLE, snapshot=snapshot, reason="strong identity parse failure")


def audit_report(old_raw, cur_raw, *, as_of, probe=fetch, workers=12):
    old, old_collisions, old_failures = build(old_raw)
    cur, cur_collisions, cur_failures = build(cur_raw)
    old_ids, cur_ids = set(old), set(cur)
    intersection = old_ids & cur_ids
    old_only = old_ids - cur_ids
    current_only = cur_ids - old_ids

    rows = []
    for sid in sorted(intersection):
        if url(old[sid]) != url(cur[sid]):
            rows.append(classify(old[sid], cur, as_of=as_of, probe=probe))
    missing_jobs = [old[sid] for sid in sorted(old_only)]
    if workers > 1 and len(missing_jobs) > 1:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            rows.extend(pool.map(lambda job: classify(job, cur, as_of=as_of, probe=probe), missing_jobs))
    else:
        rows.extend(classify(job, cur, as_of=as_of, probe=probe) for job in missing_jobs)
    rows.extend(failure_row(job, "historical") for job in old_failures)
    rows.extend(failure_row(job, "current") for job in cur_failures)

    counts = dict(sorted(Counter(item["classification"] for item in rows).items()))
    actual_missing = [item for item in rows if item["classification"] == ACTUAL_MISSING]
    unverifiable = [item for item in rows if item["classification"] == UNVERIFIABLE]
    collision_counts = {"historical": old_collisions, "current": cur_collisions}
    parse_failure_counts = {"historical": len(old_failures), "current": len(cur_failures)}
    reference_matches = len(old) == 7424 and len(cur) == 7353 and len(old_only) == 71
    healthy = not any(collision_counts.values()) and not any(parse_failure_counts.values()) and not actual_missing and not unverifiable

    return {
        "generatedAt": datetime.now(KST).isoformat(),
        "auditDate": as_of.isoformat(),
        "historicalCommit": HIST,
        "populationContract": contract_metadata(as_of=as_of),
        "rawHistoricalSupportCount": len(old_raw), "rawCurrentSupportCount": len(cur_raw),
        "historicalSupportCount": len(old), "currentSupportCount": len(cur),
        "intersectionCount": len(intersection), "oldOnlyCount": len(old_only), "currentOnlyCount": len(current_only),
        "normalizedCollisionCount": collision_counts, "identityParseFailureCount": parse_failure_counts,
        "identityParseFailureExamples": {
            "historical": [failure_row(job, "historical") for job in old_failures[:50]],
            "current": [failure_row(job, "current") for job in cur_failures[:50]],
        },
        "historicalMinusCurrent": len(old_only), "counts": counts,
        "actualMissing": actual_missing, "unverifiable": unverifiable,
        "historicalReference": {"historical": 7424, "current": 7353, "difference": 71},
        "historicalReferenceMatches": reference_matches,
        "targetPopulation": {"historical": 7424, "current": 7353, "difference": 71},
        "targetPopulationMatches": reference_matches,
        "healthCriteria": {"identityParseFailures": 0, "identityCollisions": 0, "actualMissing": 0, "unverifiable": 0, "historicalReferenceCountsAffectHealth": False},
        "healthy": healthy, "rows": rows,
    }


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--as-of", type=date.fromisoformat, default=datetime.now(KST).date())
    return parser.parse_args()


def main():
    args = parse_args()
    old_raw = [j for j in as_jobs(git_json(HIST, "jobs.json")) if is_support(j, args.as_of)]
    cur_raw = [j for j in as_jobs(json.loads(Path("jobs.json").read_text(encoding="utf-8"))) if is_support(j, args.as_of)]
    report = audit_report(old_raw, cur_raw, as_of=args.as_of)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary_keys = ("rawHistoricalSupportCount", "rawCurrentSupportCount", "historicalSupportCount", "currentSupportCount", "intersectionCount", "oldOnlyCount", "currentOnlyCount", "normalizedCollisionCount", "identityParseFailureCount", "historicalMinusCurrent", "counts", "historicalReferenceMatches", "healthy")
    print(json.dumps({key: report[key] for key in summary_keys}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["healthy"] else 2)


if __name__ == "__main__":
    main()
