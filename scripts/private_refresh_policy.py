#!/usr/bin/env python3
"""Runtime private-source policy for the single production watchdog.

The core supervisor remains the single decision engine and
``fast-refresh-watchdog.yml`` remains the only scheduled automatic dispatcher.
This wrapper:
- starts all seven user-facing private recruitment sources before freshness limits;
- keeps cultural-foundation official coverage on its own lower-priority report;
- registers LessonInfo culture-link cold verification as a guarded dispatch-only
  maintenance target when source data has advanced beyond its link proof.

Official Fast/Unified/recovery/completeness policy is intentionally untouched.
"""

from __future__ import annotations

if __package__:
    from scripts import production_supervisor as supervisor
else:
    import production_supervisor as supervisor

# Six existing direct private collectors plus the separate foundation coverage job.
# CleanEye is registered independently below so its private feed no longer waits for
# the much heavier cultural-foundation coverage workflow.
PRIVATE_REFRESH_TARGET_HOURS = {
    "private-lessoninfo": 4,
    "private-jobteacher": 4,
    "private-artmore-candidate": 4,
    "private-gonggonggangsa": 4,
    "private-seekle": 10,
    "private-boramyc": 10,
    "private-foundation": 22,
}

CLEANEYE_KEY = "private-cleaneye"
CLEANEYE_WORKFLOW = "update-cleaneye-jobs.yml"
CLEANEYE_REPORT = "cleaneye_foundation_report.json"
FOUNDATION_REPORT = "official_foundation_report.json"

LESSONINFO_LINK_KEY = "private-lessoninfo-links"
LESSONINFO_LINK_WORKFLOW = "lessoninfo-culture-cold-verify.yml"
LESSONINFO_LINK_REPORT = "lessoninfo_culture_link_report.json"
LESSONINFO_SOURCE_REPORT = "lessoninfo_reconciliation_report.json"


def apply_private_refresh_policy() -> None:
    """Add headroom to private sources without changing official collection policy."""
    current = set(supervisor.PRIVATE_REFRESH_TARGETS)
    expected = set(PRIVATE_REFRESH_TARGET_HOURS)
    missing = sorted(current - expected)
    extra = sorted(expected - current)
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

    # The legacy foundation target used CleanEye's report as its freshness proxy.
    # Once CleanEye has its own lightweight writer, foundation freshness must follow
    # the actual official-foundation report or a CleanEye refresh would falsely mark
    # the whole foundation collector fresh.
    supervisor.PRIVATE_REFRESH_TARGETS["private-foundation"]["report"] = FOUNDATION_REPORT

    supervisor.PRIVATE_REFRESH_TARGETS[CLEANEYE_KEY] = {
        "workflow": CLEANEYE_WORKFLOW,
        "report": CLEANEYE_REPORT,
        "maxAgeHours": 4,
        "hardFreshnessBudgetHours": 6,
    }
    supervisor.TARGETS[CLEANEYE_KEY] = CLEANEYE_WORKFLOW
    supervisor.PRODUCTION_EVENTS[CLEANEYE_WORKFLOW] = {"workflow_dispatch"}
    supervisor.CIRCUIT_BACKOFF_HOURS[CLEANEYE_KEY] = 6


def register_lessoninfo_link_verification() -> None:
    """Add a dispatch-only link verifier without adding a second scheduler.

    When LessonInfo source reconciliation is newer than the committed cold-link
    report, make link verification eligible after one hour. Otherwise retain a
    12-hour periodic re-verification budget for link rot. The supervisor's normal
    one-private-writer rule, failure circuit, and official-first ordering still
    decide when it may actually run.
    """
    source_at = supervisor.git_commit_time(LESSONINFO_SOURCE_REPORT)
    link_at = supervisor.git_commit_time(LESSONINFO_LINK_REPORT)
    source_advanced = bool(source_at and (link_at is None or source_at > link_at))
    refresh_hours = 1 if source_advanced else 12

    supervisor.PRIVATE_REFRESH_TARGETS[LESSONINFO_LINK_KEY] = {
        "workflow": LESSONINFO_LINK_WORKFLOW,
        "report": LESSONINFO_LINK_REPORT,
        "maxAgeHours": refresh_hours,
        "hardFreshnessBudgetHours": 12,
        "dependencyNewer": source_advanced,
    }
    supervisor.TARGETS[LESSONINFO_LINK_KEY] = LESSONINFO_LINK_WORKFLOW
    supervisor.PRODUCTION_EVENTS[LESSONINFO_LINK_WORKFLOW] = {"workflow_dispatch"}
    supervisor.CIRCUIT_BACKOFF_HOURS[LESSONINFO_LINK_KEY] = 6


def main() -> int:
    apply_private_refresh_policy()
    register_lessoninfo_link_verification()
    return supervisor.main()


if __name__ == "__main__":
    raise SystemExit(main())
