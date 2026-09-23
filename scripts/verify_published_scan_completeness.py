#!/usr/bin/env python3
"""Verify published-snapshot completeness without confusing later live arrivals with omissions.

The deep audit intentionally re-crawls all official sources long after the production snapshot was
published. New official IDs can legitimately appear during that interval. This verifier separates:

1. scan-bound completeness: every ID marked present in the published source ledger must exist in
   the published jobs snapshot; and
2. live freshness delta: IDs present only in the later independent live ledger are reported, but do
   not retroactively make the older published snapshot incomplete.

Live reconciliation must still be structurally complete and finish with missingAfter == 0. This does
not weaken freshness monitoring; the production supervisor continues to enforce Fast freshness
independently.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from stable_source_identity import canonical_source_id
    from source_registry import official_source_count
except ModuleNotFoundError:  # imported as scripts.* from unit tests
    from scripts.stable_source_identity import canonical_source_id
    from scripts.source_registry import official_source_count


REPORT_PATH = Path("published_scan_completeness_report.json")


class VerificationError(RuntimeError):
    pass


def load_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise VerificationError(f"{path}: expected JSON object")
    return value


def ledger_current_ids(ledger: dict[str, Any]) -> set[str]:
    entries = ledger.get("entries") or {}
    if not isinstance(entries, dict):
        raise VerificationError("ledger entries must be an object")
    return {
        str(sid)
        for sid, entry in entries.items()
        if isinstance(entry, dict)
        and entry.get("presentInLatestOfficialScan") is True
        and str(sid)
    }


def published_job_ids(payload: dict[str, Any]) -> set[str]:
    jobs = payload.get("jobs") or []
    if not isinstance(jobs, list) or len(jobs) < 100:
        raise VerificationError(f"published jobs snapshot is suspicious: {len(jobs) if isinstance(jobs, list) else 'invalid'}")
    return {
        sid
        for sid in (canonical_source_id(job) for job in jobs)
        if sid
    }


def _summary(report: dict[str, Any], label: str) -> dict[str, Any]:
    summary = report.get("summary") or {}
    if not isinstance(summary, dict):
        raise VerificationError(f"{label} summary missing")
    return summary


def _require_registry_complete(
    report: dict[str, Any],
    expected_sources: int,
    label: str,
) -> dict[str, Any]:
    summary = _summary(report, label)
    total = int(summary.get("totalSources") or 0)
    reconciled = int(summary.get("reconciledSources") or 0)
    missing_after = int(summary.get("missingAfter") or 0)
    incomplete = report.get("incompleteSources") or []
    if total != expected_sources or reconciled != total or incomplete:
        raise VerificationError(
            f"{label} registry incomplete: expected={expected_sources}, total={total}, "
            f"reconciled={reconciled}, incomplete={incomplete}"
        )
    if missing_after != 0:
        raise VerificationError(f"{label} reconciliation still has missingAfter={missing_after}")
    return summary


def verify(
    published_jobs: dict[str, Any],
    published_ledger: dict[str, Any],
    published_report: dict[str, Any],
    live_ledger: dict[str, Any],
    live_report: dict[str, Any],
    *,
    expected_sources: int,
) -> dict[str, Any]:
    published_summary = _require_registry_complete(
        published_report, expected_sources, "published"
    )
    live_summary = _require_registry_complete(live_report, expected_sources, "live")

    published_policy = str(published_report.get("populationPolicy") or published_summary.get("populationPolicy") or "")
    live_policy = str(live_report.get("populationPolicy") or live_summary.get("populationPolicy") or "")
    if not published_policy or published_policy != str(published_ledger.get("populationPolicy") or ""):
        raise VerificationError("published ledger/report population policy mismatch")
    if not live_policy or live_policy != str(live_ledger.get("populationPolicy") or ""):
        raise VerificationError("live ledger/report population policy mismatch")
    if published_policy != live_policy:
        raise VerificationError(
            f"population policy changed during audit: published={published_policy}, live={live_policy}"
        )

    published_generated = str(published_report.get("generatedAt") or "")
    published_ledger_generated = str(published_ledger.get("generatedAt") or "")
    if not published_generated or published_generated != published_ledger_generated:
        raise VerificationError(
            "published report/ledger are not from the same scan window: "
            f"report={published_generated!r}, ledger={published_ledger_generated!r}"
        )

    job_ids = published_job_ids(published_jobs)
    published_scan_ids = ledger_current_ids(published_ledger)
    live_scan_ids = ledger_current_ids(live_ledger)

    if int(published_ledger.get("officialIdCount") or 0) != len(published_scan_ids):
        raise VerificationError("published ledger officialIdCount does not match current-ID set")
    if int(published_summary.get("officialIdCount") or 0) != len(published_scan_ids):
        raise VerificationError("published report officialIdCount does not match published ledger")

    if int(live_ledger.get("officialIdCount") or 0) != len(live_scan_ids):
        raise VerificationError("live ledger officialIdCount does not match current-ID set")
    if int(live_summary.get("officialIdCount") or 0) != len(live_scan_ids):
        raise VerificationError("live report officialIdCount does not match live ledger")

    scan_bound_missing = sorted(published_scan_ids - job_ids)
    if scan_bound_missing:
        raise VerificationError(
            "published snapshot omitted IDs that were already present in its own official scan: "
            f"count={len(scan_bound_missing)}, examples={scan_bound_missing[:10]}"
        )

    live_missing_from_published_jobs = sorted(live_scan_ids - job_ids)
    reported_live_missing_before = int(live_summary.get("missingBefore") or 0)
    if reported_live_missing_before != len(live_missing_from_published_jobs):
        raise VerificationError(
            "live missingBefore does not match independent live-ledger/job set difference: "
            f"reported={reported_live_missing_before}, calculated={len(live_missing_from_published_jobs)}"
        )

    live_only_ids = sorted(live_scan_ids - published_scan_ids)
    if not set(live_missing_from_published_jobs).issubset(set(live_only_ids)):
        raise VerificationError(
            "live audit found an ID absent from jobs that was already in the published scan ledger"
        )

    published_payload_summary = published_jobs.get("sourceReconciliation") or {}
    if isinstance(published_payload_summary, dict) and published_payload_summary:
        for key in ("officialIdCount", "missingAfter", "reconciledSources", "totalSources"):
            if int(published_payload_summary.get(key) or 0) != int(published_summary.get(key) or 0):
                raise VerificationError(
                    f"published jobs/report reconciliation mismatch for {key}: "
                    f"jobs={published_payload_summary.get(key)}, report={published_summary.get(key)}"
                )

    return {
        "state": "complete",
        "populationPolicy": published_policy,
        "registeredOfficialSources": expected_sources,
        "publishedScan": {
            "generatedAt": published_generated,
            "officialIdCount": len(published_scan_ids),
            "missingFromPublishedJobs": 0,
        },
        "liveAudit": {
            "generatedAt": str(live_report.get("generatedAt") or ""),
            "officialIdCount": len(live_scan_ids),
            "missingBefore": reported_live_missing_before,
            "missingAfter": int(live_summary.get("missingAfter") or 0),
            "idsAbsentFromPublishedSnapshot": len(live_only_ids),
            "idsAbsentFromPublishedJobs": len(live_missing_from_published_jobs),
            "examplesAbsentFromPublishedJobs": live_missing_from_published_jobs[:20],
        },
        "interpretation": (
            "Published-scan completeness passed. Live-only IDs are freshness delta and are handled "
            "by the independent Fast freshness policy, not retroactively counted as scan-bound omissions."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--published-jobs", default="/tmp/production_jobs.json")
    parser.add_argument("--published-ledger", default="/tmp/production_source_id_ledger.json")
    parser.add_argument("--published-report", default="/tmp/production_source_reconciliation_report.json")
    parser.add_argument("--live-ledger", default="source_id_ledger.json")
    parser.add_argument("--live-report", default="source_reconciliation_report.json")
    parser.add_argument("--report", default=str(REPORT_PATH))
    args = parser.parse_args()

    result = verify(
        load_json(args.published_jobs),
        load_json(args.published_ledger),
        load_json(args.published_report),
        load_json(args.live_ledger),
        load_json(args.live_report),
        expected_sources=official_source_count(),
    )
    Path(args.report).write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
