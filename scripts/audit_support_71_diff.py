#!/usr/bin/env python3
"""Evidence-based comparison audit for the historical support-office snapshot."""
from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import scrape_jobs as production_scrape
from stable_source_identity import canonical_source_id
from support_page_evidence import official_page_evidence
from support_population_contract import contract_metadata, is_support_population_job

HIST = "432aaa232106e206d92ec6b971fd5dec979ab363"
OUT = Path("support_71_diff_audit.json")
UA = "gg-edujob/support-diff-audit"
KST = timezone(timedelta(hours=9))
LOOKBACK_DAYS = 90

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


def parse_snapshot_time(value, *, fallback_date):
    raw = str(value or "").strip()
    if raw:
        for fmt in ("%Y-%m-%d %H:%M:%S KST", "%Y-%m-%d %H:%M KST"):
            try:
                return datetime.strptime(raw, fmt).replace(tzinfo=KST)
            except ValueError:
                pass
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=KST)
            return parsed.astimezone(KST)
        except ValueError:
            pass
    return datetime.combine(fallback_date, time.min, tzinfo=KST)


def temporal_cutoff(historical_updated_at, current_updated_at, *, as_of):
    historical = parse_snapshot_time(historical_updated_at, fallback_date=as_of)
    current = parse_snapshot_time(current_updated_at, fallback_date=as_of)
    anchor = max(historical, current)
    return anchor - timedelta(days=LOOKBACK_DAYS), historical, current


def registered_value(job):
    return str(job.get("registered") or job.get("registeredAt") or "")


def align_to_cutoff(rows, cutoff):
    """Apply the production recent_enough predicate at a shared synthetic snapshot time.

    production `recent_enough` intentionally keeps blank/unparseable dates. Reusing it here keeps
    the audit's temporal semantics identical to the published 90-day collector while moving both
    snapshots onto one common lower bound.
    """
    anchor = cutoff + timedelta(days=LOOKBACK_DAYS)
    original_now = production_scrape.NOW
    production_scrape.NOW = anchor
    try:
        return [
            job for job in rows
            if production_scrape.recent_enough(
                production_scrape.date_norm(registered_value(job)), days=LOOKBACK_DAYS
            )
        ]
    finally:
        production_scrape.NOW = original_now


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


def fetch_attachment(url_, referer):
    request = Request(url_, headers={"User-Agent": UA, "Referer": referer})
    with urlopen(request, timeout=30) as response:
        return response.read(10_000_000)


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
    old_id = identity(old)
    result = {
        "oldId": old_id,
        "identityType": old_id.split(":", 1)[0] if old_id else "",
        "source": str(old.get("source") or ""),
        "historicalApplyEnd": str(old.get("applyEnd") or old.get("deadline") or ""),
        "classification": classification,
        "title": title(old),
        "url": url(old),
    }
    result.update(evidence)
    return result


def redirected_identity(old, final_url):
    candidate = dict(old)
    candidate["url"] = final_url
    candidate.pop("openUrl", None)
    candidate.pop("openParams", None)
    return identity(candidate)


def classify(old, current, *, as_of, probe=fetch, attachment_loader=fetch_attachment):
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
    probe_evidence = {"http": http, "finalUrl": final_url, "redirected": final_url != url(old)}
    if http in (404, 410) or any(marker in body for marker in DELETION_MARKERS):
        return row(old, OFFICIAL_ENDED, **probe_evidence)

    final_id = redirected_identity(old, final_url)
    if final_id and final_id != oid and final_id in current:
        moved = current[final_id]
        return row(old, CANONICAL_URL_MOVE, newId=final_id, newUrl=url(moved), newTitle=title(moved), evidence="official redirect resolves to current canonical detail identity", **probe_evidence)

    page_evidence = official_page_evidence(
        body,
        oid,
        final_url,
        as_of=as_of,
        attachment_loader=attachment_loader,
    )
    if page_evidence and page_evidence["kind"] == "ended":
        return row(old, OFFICIAL_ENDED, officialEvidence=page_evidence, **probe_evidence)
    if page_evidence and page_evidence["kind"] == "deadline":
        official_end = parse_date(page_evidence.get("date"))
        if official_end is not None and official_end < as_of:
            return row(old, EXPIRED, applyEnd=official_end.isoformat(), officialEvidence=page_evidence, **probe_evidence)
        if official_end is not None and official_end >= as_of:
            return row(old, ACTUAL_MISSING, applyEnd=official_end.isoformat(), officialEvidence=page_evidence, **probe_evidence)

    if 200 <= http < 400 and end is not None and end >= as_of:
        return row(old, ACTUAL_MISSING, applyEnd=end.isoformat(), evidence="official detail is reachable before its deadline", **probe_evidence)

    reason = "reachable page has no valid active deadline" if 200 <= http < 400 else "ambiguous official response"
    return row(old, UNVERIFIABLE, reason=reason, **probe_evidence)


def failure_row(job, snapshot):
    return row(job, UNVERIFIABLE, snapshot=snapshot, reason="strong identity parse failure")


def audit_report(
    old_raw,
    cur_raw,
    *,
    as_of,
    historical_updated_at=None,
    current_updated_at=None,
    probe=fetch,
    attachment_loader=fetch_attachment,
    workers=12,
):
    cutoff, historical_time, current_time = temporal_cutoff(
        historical_updated_at, current_updated_at, as_of=as_of
    )

    raw_old, raw_old_collisions, raw_old_failures = build(old_raw)
    raw_cur, raw_cur_collisions, raw_cur_failures = build(cur_raw)
    raw_old_ids, raw_cur_ids = set(raw_old), set(raw_cur)
    raw_old_only = raw_old_ids - raw_cur_ids
    raw_current_only = raw_cur_ids - raw_old_ids

    old_aligned_raw = align_to_cutoff(old_raw, cutoff)
    cur_aligned_raw = align_to_cutoff(cur_raw, cutoff)
    old, old_collisions, old_failures = build(old_aligned_raw)
    cur, cur_collisions, cur_failures = build(cur_aligned_raw)
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
            rows.extend(pool.map(lambda job: classify(job, cur, as_of=as_of, probe=probe, attachment_loader=attachment_loader), missing_jobs))
    else:
        rows.extend(classify(job, cur, as_of=as_of, probe=probe, attachment_loader=attachment_loader) for job in missing_jobs)
    rows.extend(failure_row(job, "historical") for job in old_failures)
    rows.extend(failure_row(job, "current") for job in cur_failures)

    counts = dict(sorted(Counter(item["classification"] for item in rows).items()))
    actual_missing = [item for item in rows if item["classification"] == ACTUAL_MISSING]
    unverifiable = [item for item in rows if item["classification"] == UNVERIFIABLE]
    collision_counts = {"historical": old_collisions, "current": cur_collisions}
    parse_failure_counts = {"historical": len(old_failures), "current": len(cur_failures)}
    raw_collision_counts = {"historical": raw_old_collisions, "current": raw_cur_collisions}
    raw_parse_failure_counts = {"historical": len(raw_old_failures), "current": len(raw_cur_failures)}
    reference_matches = len(raw_old) == 7424 and len(raw_cur) == 7353 and len(raw_old_only) == 71
    temporal_alignment_applied = cutoff is not None
    healthy = (
        temporal_alignment_applied
        and not any(collision_counts.values())
        and not any(parse_failure_counts.values())
        and not actual_missing
        and not unverifiable
    )

    return {
        "generatedAt": datetime.now(KST).isoformat(),
        "auditDate": as_of.isoformat(),
        "historicalCommit": HIST,
        "populationContract": contract_metadata(as_of=as_of),
        "temporalAlignment": {
            "applied": temporal_alignment_applied,
            "lookbackDays": LOOKBACK_DAYS,
            "historicalUpdatedAt": historical_time.isoformat(),
            "currentUpdatedAt": current_time.isoformat(),
            "appliedCutoff": cutoff.isoformat(),
            "policy": "both snapshots use the production recent_enough predicate against the same lower bound; blank/unparseable registration dates remain included",
        },
        "appliedCutoff": cutoff.isoformat(),
        "rawHistoricalSupportCount": len(raw_old),
        "rawCurrentSupportCount": len(raw_cur),
        "historicalSupportCount": len(old),
        "currentSupportCount": len(cur),
        "rawOldOnly": len(raw_old_only),
        "alignedOldOnly": len(old_only),
        "rawCurrentOnly": len(raw_current_only),
        "alignedCurrentOnly": len(current_only),
        "intersectionCount": len(intersection),
        "oldOnlyCount": len(old_only),
        "currentOnlyCount": len(current_only),
        "normalizedCollisionCount": collision_counts,
        "identityParseFailureCount": parse_failure_counts,
        "rawNormalizedCollisionCount": raw_collision_counts,
        "rawIdentityParseFailureCount": raw_parse_failure_counts,
        "identityParseFailureExamples": {
            "historical": [failure_row(job, "historical") for job in old_failures[:50]],
            "current": [failure_row(job, "current") for job in cur_failures[:50]],
        },
        "historicalMinusCurrent": len(old_only),
        "counts": counts,
        "actualMissing": actual_missing,
        "unverifiable": unverifiable,
        "historicalReference": {"historical": 7424, "current": 7353, "difference": 71},
        "historicalReferenceMatches": reference_matches,
        "targetPopulation": {"historical": 7424, "current": 7353, "difference": 71},
        "targetPopulationMatches": reference_matches,
        "healthCriteria": {
            "temporalAlignmentApplied": True,
            "identityParseFailures": 0,
            "identityCollisions": 0,
            "actualMissing": 0,
            "unverifiable": 0,
            "historicalReferenceCountsAffectHealth": False,
        },
        "healthy": healthy,
        "rows": rows,
    }


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--as-of", type=date.fromisoformat, default=datetime.now(KST).date())
    return parser.parse_args()


def main():
    args = parse_args()
    historical_payload = git_json(HIST, "jobs.json")
    current_payload = json.loads(Path("jobs.json").read_text(encoding="utf-8"))
    old_raw = [j for j in as_jobs(historical_payload) if is_support(j, args.as_of)]
    cur_raw = [j for j in as_jobs(current_payload) if is_support(j, args.as_of)]
    report = audit_report(
        old_raw,
        cur_raw,
        as_of=args.as_of,
        historical_updated_at=(historical_payload.get("updatedAt") if isinstance(historical_payload, dict) else None),
        current_updated_at=(current_payload.get("updatedAt") if isinstance(current_payload, dict) else None),
    )
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary_keys = (
        "rawHistoricalSupportCount", "rawCurrentSupportCount",
        "historicalSupportCount", "currentSupportCount",
        "rawOldOnly", "alignedOldOnly", "rawCurrentOnly", "alignedCurrentOnly",
        "appliedCutoff", "intersectionCount", "oldOnlyCount", "currentOnlyCount",
        "normalizedCollisionCount", "identityParseFailureCount", "historicalMinusCurrent",
        "counts", "historicalReferenceMatches", "healthy",
    )
    print(json.dumps({key: report[key] for key in summary_keys}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["healthy"] else 2)


if __name__ == "__main__":
    main()
