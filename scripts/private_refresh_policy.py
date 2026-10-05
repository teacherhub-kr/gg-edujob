#!/usr/bin/env python3
"""Runtime private-source policy for the single production watchdog.

The core supervisor remains the single decision engine and
``fast-refresh-watchdog.yml`` remains the only scheduled automatic dispatcher.
This wrapper:
- starts all seven user-facing private recruitment sources before freshness limits;
- keeps cultural-foundation official coverage on its own lower-priority report;
- registers LessonInfo culture-link cold verification as a guarded dispatch-only
  maintenance target when source data has advanced beyond its link proof;
- prevents a private-only Unified rebuild from publishing a newer LessonInfo
  snapshot before its cold-link proof catches up.

Official Fast/Unified/recovery/completeness policy is intentionally untouched.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

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


def lessoninfo_link_verification_should_precede_unified(
    state: dict[str, Any], now, repo: str
) -> bool:
    """Return True when a private-only Unified rebuild must wait for link proof.

    Official jobs always keep publication priority. This guard only intercepts a
    Unified action when ``jobs.json`` itself is already represented in
    ``unified_jobs.json`` and the action is being driven by private-source input.
    """
    if state.get("action") != "unified":
        return False

    source_at = supervisor.git_commit_time(LESSONINFO_SOURCE_REPORT)
    link_at = supervisor.git_commit_time(LESSONINFO_LINK_REPORT)
    source_advanced = bool(source_at and (link_at is None or source_at > link_at))
    if not source_advanced:
        return False

    # Never delay newer official jobs for a private link-maintenance dependency.
    jobs_at = supervisor.git_commit_time("jobs.json")
    unified_at = supervisor.git_commit_time("unified_jobs.json")
    if supervisor.unified_publication_stale(jobs_at, unified_at):
        return False

    freshness = (state.get("privateFreshness") or {}).get(LESSONINFO_LINK_KEY) or {}
    if not freshness.get("overdue"):
        return False
    if state.get("activePrivateTargets"):
        return False

    runs = supervisor.gh_runs(repo, LESSONINFO_LINK_WORKFLOW)
    blocked, _, _ = supervisor.circuit_blocked(LESSONINFO_LINK_KEY, runs, now)
    if blocked:
        return False

    latest = supervisor.latest_completed(runs)
    latest_at = supervisor.completed_at(latest)
    if (
        latest
        and latest.get("conclusion") in supervisor.REAL_FAILURES
        and latest_at
        and now - latest_at < timedelta(hours=1)
    ):
        return False
    return True


def install_lessoninfo_publication_dependency_guard() -> None:
    """Keep LessonInfo's collect -> cold-verify -> private-publish order atomic."""
    original_compute_state = supervisor.compute_state

    def guarded_compute_state(now, repo: str):
        state = original_compute_state(now, repo)
        if lessoninfo_link_verification_should_precede_unified(state, now, repo):
            state["action"] = LESSONINFO_LINK_KEY
            state["reason"] = (
                "LessonInfo source advanced beyond its cold-link proof; "
                "verify links before a private-only Unified publication"
            )
            state["circuit"] = None
        return state

    supervisor.compute_state = guarded_compute_state


def main() -> int:
    apply_private_refresh_policy()
    register_lessoninfo_link_verification()
    install_lessoninfo_publication_dependency_guard()
    return supervisor.main()


if __name__ == "__main__":
    raise SystemExit(main())