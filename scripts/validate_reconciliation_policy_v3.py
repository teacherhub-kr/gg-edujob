#!/usr/bin/env python3
"""Run the existing reconciliation guard under the three-region/39-source policy.

The first deployment legitimately adds a new official region to a baseline that had zero Incheon
rows. Keep the legacy 10% shape guard for Seoul/Gyeonggi, and widen only the total-growth allowance
for that one migration after proving every excess row is attributable to Incheon.
"""
import json
from pathlib import Path

import validate_reconciliation_policy as base

base.POLICY = "stable-id-39-v3-metro-central-90d"


def _jobs(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return data.get("jobs", []) if isinstance(data, dict) and isinstance(data.get("jobs"), list) else []
    except Exception:
        return []


def _prepare_first_incheon_migration():
    if not base.FAST_BASELINE.exists():
        return
    previous = _jobs(base.FAST_BASELINE)
    current = _jobs(base.ROOT / "jobs.json")
    if not previous or not current:
        return

    previous_incheon = [job for job in previous if job.get("province") == "인천"]
    current_incheon = [job for job in current if job.get("province") == "인천"]
    if previous_incheon or not current_incheon:
        return

    previous_legacy = len(previous)
    current_legacy = sum(1 for job in current if job.get("province") != "인천")
    low = int(previous_legacy * (1.0 - base.MAX_FAST_DROP_RATIO))
    high = int(previous_legacy * (1.0 + base.MAX_FAST_GROWTH_RATIO))
    if current_legacy < low or current_legacy > high:
        raise SystemExit(
            "Refusing first Incheon migration because the pre-existing Seoul/Gyeonggi population "
            f"changed outside the normal guard: previous={previous_legacy}, currentLegacy={current_legacy}, "
            f"allowed=[{low},{high}]"
        )

    total_growth = max(0.0, (len(current) - len(previous)) / max(len(previous), 1))
    # Allow exactly the observed registry-expansion envelope plus a small rounding margin. The
    # 39-source reconciliation and required-region guard still have to pass in the same run.
    base.MAX_FAST_GROWTH_RATIO = max(base.MAX_FAST_GROWTH_RATIO, total_growth + 0.01)
    print(
        "First Incheon migration shape accepted: "
        f"legacy={previous_legacy}->{current_legacy}, incheonAdded={len(current_incheon)}, "
        f"temporaryTotalGrowthRatio={base.MAX_FAST_GROWTH_RATIO:.3f}"
    )


if __name__ == "__main__":
    _prepare_first_incheon_migration()
    base.main()
