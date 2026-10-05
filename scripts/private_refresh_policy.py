#!/usr/bin/env python3
"""Apply pre-deadline freshness targets for private recruitment sources.

The core production supervisor remains the single decision engine and the
scheduled watchdog remains the single automatic dispatcher.  This wrapper only
tightens private-source refresh ages so a collector starts before the previous
hard freshness budget is exhausted.
"""

from __future__ import annotations

from scripts import production_supervisor as supervisor

# Keep a two-hour operating margin ahead of the prior 6/12/24-hour limits.
# Official Fast/Unified/recovery/completeness policy is intentionally untouched.
PRIVATE_REFRESH_TARGET_HOURS = {
    "private-lessoninfo": 4,
    "private-jobteacher": 4,
    "private-artmore-candidate": 4,
    "private-gonggonggangsa": 4,
    "private-seekle": 10,
    "private-boramyc": 10,
    "private-foundation": 22,
}


def apply_private_refresh_policy() -> None:
    missing = sorted(set(supervisor.PRIVATE_REFRESH_TARGETS) - set(PRIVATE_REFRESH_TARGET_HOURS))
    extra = sorted(set(PRIVATE_REFRESH_TARGET_HOURS) - set(supervisor.PRIVATE_REFRESH_TARGETS))
    if missing or extra:
        raise RuntimeError(
            f"private refresh policy mismatch: missing={missing}, extra={extra}"
        )

    for key, refresh_hours in PRIVATE_REFRESH_TARGET_HOURS.items():
        spec = supervisor.PRIVATE_REFRESH_TARGETS[key]
        previous_limit = int(spec["maxAgeHours"])
        if refresh_hours <= 0 or refresh_hours >= previous_limit:
            raise RuntimeError(
                f"invalid pre-deadline target for {key}: {refresh_hours} >= {previous_limit}"
            )
        spec["hardFreshnessBudgetHours"] = previous_limit
        spec["maxAgeHours"] = refresh_hours


def main() -> int:
    apply_private_refresh_policy()
    return supervisor.main()


if __name__ == "__main__":
    raise SystemExit(main())
