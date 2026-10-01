#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))
UNIFIED = Path("unified_jobs.json")
SEARCH_REPORT = Path("unified_search_report.json")
COVERAGE_REPORT = Path("cultural_foundation_coverage_report.json")


def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def mark_foundation_degraded() -> dict:
    unified = load(UNIFIED)
    search = load(SEARCH_REPORT)
    coverage = load(COVERAGE_REPORT)

    if coverage.get("healthy") is True:
        raise ValueError("foundation coverage is healthy; degradation marker is not allowed")

    before_jobs = unified.get("jobs")
    if not isinstance(before_jobs, list):
        raise ValueError("unified_jobs.json has no jobs list")

    generated_at = datetime.now(KST).isoformat(timespec="seconds")
    detail = {
        "healthy": False,
        "mode": "validated-current-rows-only",
        "reason": "foundation-coverage-reconciliation-failed",
        "coverageGapCount": int(coverage.get("coverageGapCount") or 0),
        "failedAvailableComponents": list(coverage.get("failedAvailableComponents") or []),
        "coverageReportGeneratedAt": coverage.get("generatedAt"),
        "markedAt": generated_at,
    }

    degraded = set(str(x) for x in (unified.get("degradedSections") or []) if str(x))
    degraded.add("foundation")
    unified["degradedSections"] = sorted(degraded)
    section_health = dict(unified.get("sectionHealth") or {})
    section_health["foundation"] = detail
    unified["sectionHealth"] = section_health

    report_degraded = set(str(x) for x in (search.get("degradedSections") or []) if str(x))
    report_degraded.add("foundation")
    search["degradedSections"] = sorted(report_degraded)
    search["foundationCoverageHealthy"] = False
    search["foundationCoverageGapCount"] = detail["coverageGapCount"]
    search["foundationFailedAvailableComponents"] = detail["failedAvailableComponents"]
    search["foundationDegradationMode"] = detail["mode"]
    search["foundationCoverageReportGeneratedAt"] = detail["coverageReportGeneratedAt"]
    search["publicationPolicy"] = "core-official-independent-foundation-degradation-v1"

    # This step must never mutate the already validated candidate rows. Its only
    # purpose is to make the degraded foundation coverage explicit while allowing
    # the 44-source education-official publication to proceed.
    if unified.get("jobs") != before_jobs:
        raise AssertionError("foundation degradation annotation mutated jobs")

    UNIFIED.write_text(json.dumps(unified, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    SEARCH_REPORT.write_text(json.dumps(search, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {
        "degradedSection": "foundation",
        "coverageGapCount": detail["coverageGapCount"],
        "failedAvailableComponents": detail["failedAvailableComponents"],
        "jobsUnchanged": True,
    }
    print(json.dumps(summary, ensure_ascii=False))
    return summary


def main() -> int:
    mark_foundation_degraded()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
