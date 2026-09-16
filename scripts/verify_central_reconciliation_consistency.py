#!/usr/bin/env python3
"""Fail closed when central-source completeness proofs are logically inconsistent.

There are deliberately three proofs:
1) `central_pagination_report.json` independently proves the current Gyeonggi and Seoul central
   list endpoints parse and paginate correctly.
2) `source_reconciliation_report.json` defines the authoritative recent population across every
   registered official source, including Incheon.
3) `gyeonggi_central_90d_report.json` is produced by an explicit independent traversal before this
   verifier runs. This verifier is read-only.

The public boards are live during an audit that can take tens of minutes, so exact count equality
between two complete scans is not a valid invariant. We allow only small bounded temporal drift
between the independent Gyeonggi/Seoul scans; Incheon completeness is enforced by its per-source
reconciliation evidence and the required-region guard.
"""
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CENTRAL = ROOT / "central_pagination_report.json"
RECON = ROOT / "source_reconciliation_report.json"
GG90 = ROOT / "gyeonggi_central_90d_report.json"
SOURCES = ROOT / "sources.json"
KST = timezone(timedelta(hours=9))
MAX_SKEW_MINUTES = 45
MAX_DRIFT_RATIO = 0.01
MAX_DRIFT_ABSOLUTE = 25
MIN_DRIFT_ABSOLUTE = 3


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def official_source_count() -> int:
    """Count the live canonical registry without relying on script-directory import state."""
    registry = load(SOURCES)
    if not isinstance(registry, dict) or not registry:
        raise SystemExit("Official source registry is empty or malformed")
    total = 0
    for key, group in registry.items():
        if not isinstance(group, dict):
            raise SystemExit(f"Malformed official source group: {key}")
        central = group.get("central")
        support = group.get("supportOffices") or []
        if central is not None and not isinstance(central, dict):
            raise SystemExit(f"Malformed central source: {key}")
        if not isinstance(support, list):
            raise SystemExit(f"Malformed support-office registry: {key}")
        total += (1 if central else 0) + len(support)
    if total <= 0:
        raise SystemExit("Official source registry resolved to zero sources")
    return total


def parse_kst(value):
    return datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S KST").replace(tzinfo=KST)


def source_map(report):
    return {str(x.get("name") or ""): x for x in (report.get("sources") or [])}


def drift_limit(a, b):
    base = max(int(a or 0), int(b or 0), 1)
    return min(MAX_DRIFT_ABSOLUTE, max(MIN_DRIFT_ABSOLUTE, math.ceil(base * MAX_DRIFT_RATIO)))


def within_live_drift(a, b):
    return abs(int(a) - int(b)) <= drift_limit(a, b)


def main():
    central = load(CENTRAL)
    recon = load(RECON)
    if not central.get("complete"):
        raise SystemExit("Central pagination report is not complete")
    expected_sources = official_source_count()
    reconciled_sources = int((recon.get("summary") or {}).get("reconciledSources") or 0)
    total_sources = int((recon.get("summary") or {}).get("totalSources") or 0)
    if reconciled_sources != expected_sources or total_sources != expected_sources:
        raise SystemExit(
            f"Registry reconciliation is not complete: registry={expected_sources}, "
            f"reconciled={reconciled_sources}, total={total_sources}"
        )
    if int((recon.get("summary") or {}).get("missingAfter") or 0) != 0:
        raise SystemExit("Registry reconciliation still has missing IDs")

    if not GG90.exists() or GG90.stat().st_size < 100:
        raise SystemExit("Independent Gyeonggi 90-day proof artifact missing")
    gg90 = load(GG90)
    if not gg90.get("complete"):
        raise SystemExit("Independent Gyeonggi 90-day report is not complete")

    try:
        ctime = parse_kst(central.get("generatedAt"))
        rtime = parse_kst(recon.get("generatedAt"))
        gtime = parse_kst(gg90.get("generatedAt"))
    except Exception as exc:
        raise SystemExit(f"Cannot prove audit timestamp consistency: {type(exc).__name__}")

    skew_cr = abs((ctime - rtime).total_seconds()) / 60
    skew_gr = abs((gtime - rtime).total_seconds()) / 60
    if skew_cr > MAX_SKEW_MINUTES:
        raise SystemExit(f"Central/reconciliation reports are from different audit windows: {skew_cr:.1f} minutes")
    if skew_gr > MAX_SKEW_MINUTES:
        raise SystemExit(f"Gyeonggi-90d/reconciliation reports are from different audit windows: {skew_gr:.1f} minutes")

    recon_sources = source_map(recon)
    central_sources = source_map(central)
    gg_name = "경기도교육청 통합 구인구직"
    se_name = "서울교육일자리포털"
    ice_name = "인천광역시교육청 채용공고"
    gg_recon = recon_sources.get(gg_name)
    se_recon = recon_sources.get(se_name)
    ice_recon = recon_sources.get(ice_name)
    gg_active = central_sources.get(gg_name)
    se_central = central_sources.get(se_name)
    if not all((gg_recon, se_recon, ice_recon, gg_active, se_central)):
        raise SystemExit("Missing one or more required central source records from verification reports")
    if ice_recon.get("coverageComplete") is not True or ice_recon.get("reconciled") is not True:
        raise SystemExit("Incheon official central reconciliation is incomplete")

    gg_recent_count = int(gg_recon.get("officialIdCount") or 0)
    gg_independent_count = int(gg90.get("stableIdCount") or 0)
    gg_active_count = int(gg_active.get("stableIdCount") or 0)
    se_recon_count = int(se_recon.get("officialIdCount") or 0)
    se_independent_count = int(se_central.get("stableIdCount") or 0)
    ice_recon_count = int(ice_recon.get("officialIdCount") or 0)

    errors = []
    if ice_recon_count <= 0:
        errors.append({"source": ice_name, "reason": "zero-official-ids"})
    if not within_live_drift(gg_independent_count, gg_recent_count):
        errors.append({
            "source": gg_name,
            "reason": "independent-90d-drift-exceeds-live-window",
            "reconciliation90d": gg_recent_count,
            "independent90d": gg_independent_count,
            "difference": abs(gg_independent_count - gg_recent_count),
            "allowedDifference": drift_limit(gg_independent_count, gg_recent_count),
        })
    if gg_active_count > max(gg_recent_count, gg_independent_count):
        errors.append({
            "source": gg_name,
            "reason": "active-count-exceeds-90d",
            "active": gg_active_count,
            "reconciliation90d": gg_recent_count,
            "independent90d": gg_independent_count,
        })
    if not within_live_drift(se_independent_count, se_recon_count):
        errors.append({
            "source": se_name,
            "reason": "central-drift-exceeds-live-window",
            "reconciliation": se_recon_count,
            "independent": se_independent_count,
            "difference": abs(se_independent_count - se_recon_count),
            "allowedDifference": drift_limit(se_independent_count, se_recon_count),
        })

    if errors:
        raise SystemExit("Central population consistency failed: " + json.dumps(errors, ensure_ascii=False))

    print(json.dumps({
        "state": "ok",
        "policy": "complete independent scans may differ only by bounded live-source drift",
        "registrySources": expected_sources,
        "timestampSkewMinutes": {
            "centralVsReconciliation": round(skew_cr, 2),
            "gyeonggi90dVsReconciliation": round(skew_gr, 2),
        },
        "sources": [
            {
                "name": gg_name,
                "activeStableIds": gg_active_count,
                "reconciliation90dStableIds": gg_recent_count,
                "independent90dStableIds": gg_independent_count,
                "difference": abs(gg_independent_count - gg_recent_count),
                "allowedDifference": drift_limit(gg_independent_count, gg_recent_count),
            },
            {
                "name": se_name,
                "reconciliationStableIds": se_recon_count,
                "independentStableIds": se_independent_count,
                "difference": abs(se_independent_count - se_recon_count),
                "allowedDifference": drift_limit(se_independent_count, se_recon_count),
            },
            {
                "name": ice_name,
                "reconciliation90dStableIds": ice_recon_count,
                "coverageComplete": True,
            },
        ],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
