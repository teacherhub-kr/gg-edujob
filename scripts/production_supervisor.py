#!/usr/bin/env python3
"""Production operations supervisor for unattended 수도권에듀잡 operation.

The supervisor is intentionally read/decision oriented:
- one scheduled watchdog owns all automatic dispatches;
- writer workflows stay workflow_dispatch-only;
- repeated real failures open a circuit instead of retrying forever;
- GitHub issues are the durable incident/heartbeat surface, not status commits;
- source-volume anomalies are compared against the previous committed reconciliation report.

It never edits recruitment data or source code.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

KST = timezone(timedelta(hours=9))
ACTIVE_STATES = {"queued", "in_progress", "waiting", "requested", "pending"}
REAL_FAILURES = {"failure", "timed_out", "startup_failure"}
FAST_REFRESH_AFTER = timedelta(hours=3, minutes=15)
P0_STALE_AFTER = timedelta(hours=6)
WATCHDOG_LIVENESS_AFTER = timedelta(hours=1, minutes=30)
WATCHDOG_WORKFLOW = "fast-refresh-watchdog.yml"
REQUIRED_REGISTRY_MINIMUMS = {"gyeonggi": 26, "seoul": 12, "incheon": 1}
INCHEON_REQUIRED_BOARD_IDS = {"1981", "1534"}

CORE_TARGETS = {
    "fast": "update-jobs.yml",
    "recovery": "recover-missing-jobs.yml",
    "completeness": "official-completeness-audit.yml",
    "unified": "unified-search.yml",
}
PRIVATE_REFRESH_TARGETS = {
    "private-lessoninfo": {
        "workflow": "update-lessoninfo-jobs.yml",
        "report": "lessoninfo_reconciliation_report.json",
        "maxAgeHours": 6,
    },
    "private-jobteacher": {
        "workflow": "update-jobteacher-jobs.yml",
        "report": "jobteacher_reconciliation_report.json",
        "maxAgeHours": 6,
    },
    "private-artmore-candidate": {
        "workflow": "update-artmore-candidate.yml",
        # Candidate freshness must follow the isolated candidate report, not the
        # canonical ArtMore publication. Otherwise a healthy candidate refresh
        # still looks stale until promotion succeeds, causing the supervisor to
        # re-run the same candidate workflow and starve other private sources.
        "report": "artmore_reconciliation_report.candidate.json",
        "maxAgeHours": 6,
    },
    "private-gonggonggangsa": {
        "workflow": "update-gonggonggangsa-jobs.yml",
        "report": "gonggonggangsa_reconciliation_report.json",
        "maxAgeHours": 6,
    },
    "private-seekle": {
        "workflow": "update-seekle-instructor-jobs.yml",
        "report": "seekle_reconciliation_report.json",
        "maxAgeHours": 12,
    },
    "private-boramyc": {
        "workflow": "update-boramyc-instructor-jobs.yml",
        "report": "boramyc_reconciliation_report.json",
        "maxAgeHours": 12,
    },
    "private-foundation": {
        "workflow": "cultural-foundation-coverage.yml",
        "report": "cleaneye_foundation_report.json",
        "maxAgeHours": 24,
    },
}
ARTMORE_PROMOTE_KEY = "private-artmore-promote"
ARTMORE_PROMOTE_WORKFLOW = "promote-artmore.yml"
PRIVATE_REFRESH_IDLE_ACTIONS = {
    "skip-healthy",
    # When verified official production is already fresh enough that execution
    # reaches an otherwise idle/backed-off branch, overdue private recruitment
    # sources may use that slot. A runnable Fast or Unified action still wins;
    # only blocked/backed-off Unified is treated as idle.
    "recovery",
    "completeness",
    "skip-recovery-circuit-open",
    "skip-recovery-backoff",
    "skip-completeness-circuit-open",
    "skip-unified-circuit-open",
    "skip-unified-backoff",
}
TARGETS = {
    **CORE_TARGETS,
    **{key: spec["workflow"] for key, spec in PRIVATE_REFRESH_TARGETS.items()},
    ARTMORE_PROMOTE_KEY: ARTMORE_PROMOTE_WORKFLOW,
}
PRODUCTION_EVENTS = {
    filename: {"workflow_dispatch"} for filename in TARGETS.values()
}
PRODUCTION_EVENTS[WATCHDOG_WORKFLOW] = {"workflow_dispatch", "schedule"}
CIRCUIT_BACKOFF_HOURS = {
    "fast": 6,
    "recovery": 12,
    "completeness": 6,
    "unified": 6,
    **{key: 6 for key in PRIVATE_REFRESH_TARGETS},
    ARTMORE_PROMOTE_KEY: 6,
}
P0_TITLE = "[AUTO][P0] Production recruitment pipeline incident"
P1_TITLE = "[AUTO][P1] Official source volume anomaly"


def load_json(path: str | Path, default: Any) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=KST)
    return dt.astimezone(KST)


def registry_contract_status(
    registry: dict[str, Any], jobs_payload: dict[str, Any]
) -> tuple[bool, dict[str, Any]]:
    """Validate the minimum official-source registry contract used by production.

    This deliberately checks more than the three top-level region keys:
    each mandatory region needs a valid central source, the known source-network
    floor must be present, Incheon's two mandatory boards must be registered,
    and the published dataset must agree with the current registry count.
    """
    reasons: list[str] = []
    breakdown: dict[str, int] = {}

    for key, minimum in REQUIRED_REGISTRY_MINIMUMS.items():
        group = registry.get(key) if isinstance(registry, dict) else None
        if not isinstance(group, dict):
            reasons.append(f"{key}:missing-group")
            breakdown[key] = 0
            continue
        central = group.get("central")
        support = group.get("supportOffices") or []
        if not isinstance(central, dict) or not str(central.get("url") or "").startswith("https://"):
            reasons.append(f"{key}:invalid-central")
            central_count = 0
        else:
            central_count = 1
        if not isinstance(support, list):
            reasons.append(f"{key}:invalid-support-list")
            support = []
        count = central_count + len(support)
        breakdown[key] = count
        if count < minimum:
            reasons.append(f"{key}:source-count={count}<minimum={minimum}")

    incheon = registry.get("incheon") if isinstance(registry, dict) else None
    incheon_central = incheon.get("central") if isinstance(incheon, dict) else None
    registered_boards = {
        str(item.get("bbsId") or "")
        for item in ((incheon_central or {}).get("requiredBoards") or [])
        if isinstance(item, dict)
    }
    missing_incheon = sorted(INCHEON_REQUIRED_BOARD_IDS - registered_boards)
    if missing_incheon:
        reasons.append("incheon:missing-required-boards=" + ",".join(missing_incheon))

    total = sum(breakdown.values())
    try:
        published = int(jobs_payload.get("officialSourceCount") or 0)
    except Exception:
        published = 0
    if published <= 0:
        reasons.append("published:officialSourceCount-missing")
    elif published != total:
        reasons.append(f"published:officialSourceCount={published}!=registry={total}")

    details = {
        "breakdown": breakdown,
        "totalOfficialSources": total,
        "publishedOfficialSourceCount": published or None,
        "reasons": reasons,
    }
    return not reasons, details


def latest_verified_production_success(
    collector_status: dict[str, Any],
) -> tuple[datetime | None, str | None]:
    candidates: list[tuple[datetime, str]] = []
    if not isinstance(collector_status, dict):
        return None, None
    for key in ("fast", "recovery"):
        item = collector_status.get(key)
        if not isinstance(item, dict):
            continue
        success_at = parse_time(item.get("lastSuccessAt"))
        if success_at is not None:
            candidates.append((success_at, key))
    if not candidates:
        return None, None
    return max(candidates, key=lambda item: item[0])


def watchdog_schedule_lag(previous_completed_at: datetime | None, now: datetime) -> bool:
    if previous_completed_at is None:
        return True
    return now - previous_completed_at > WATCHDOG_LIVENESS_AFTER


def completed_at(run: dict[str, Any] | None) -> datetime | None:
    if not run:
        return None
    return parse_time(run.get("updated_at") or run.get("run_started_at") or run.get("created_at"))


def run_started_at(run: dict[str, Any] | None) -> datetime | None:
    if not run:
        return None
    return parse_time(run.get("run_started_at") or run.get("created_at") or run.get("updated_at"))


def sort_runs_newest_first(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    floor = datetime.min.replace(tzinfo=KST)
    return sorted(runs, key=lambda run: run_started_at(run) or floor, reverse=True)


def production_runs(filename: str, runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    allowed = PRODUCTION_EVENTS[filename]
    filtered = [
        run
        for run in runs
        if run.get("event") in allowed and run.get("head_branch") == "main"
    ]
    return sort_runs_newest_first(filtered)


def latest_completed(runs: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next((r for r in sort_runs_newest_first(runs) if r.get("status") == "completed"), None)


def latest_success(runs: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next(
        (
            r
            for r in sort_runs_newest_first(runs)
            if r.get("status") == "completed" and r.get("conclusion") == "success"
        ),
        None,
    )


def consecutive_real_failures(runs: list[dict[str, Any]]) -> tuple[int, datetime | None]:
    """Count real failures since the most recent success.

    cancelled/skipped/neutral runs are ignored so maintenance cancellations do not
    masquerade as collector failures.
    """
    count = 0
    latest_failure: datetime | None = None
    for run in sort_runs_newest_first(runs):
        if run.get("status") != "completed":
            continue
        conclusion = str(run.get("conclusion") or "")
        if conclusion == "success":
            break
        if conclusion in REAL_FAILURES:
            count += 1
            if latest_failure is None:
                latest_failure = completed_at(run)
    return count, latest_failure


def circuit_blocked(
    key: str,
    runs: list[dict[str, Any]],
    now: datetime,
    *,
    allow_probe_after_change: bool = False,
) -> tuple[bool, int, datetime | None]:
    failures, latest_failure = consecutive_real_failures(runs)
    if failures < 3 or latest_failure is None:
        return False, failures, latest_failure
    if allow_probe_after_change:
        return False, failures, latest_failure
    backoff = timedelta(hours=CIRCUIT_BACKOFF_HOURS.get(key, 6))
    return now - latest_failure < backoff, failures, latest_failure


def recovery_fallback_available(
    runs: list[dict[str, Any]],
    now: datetime,
    *,
    allow_probe_after_change: bool = False,
) -> tuple[bool, str, int]:
    """Return whether Recovery may serve as a fresh-runner alternative after Fast circuit opens."""
    blocked, failures, _ = circuit_blocked(
        "recovery",
        runs,
        now,
        allow_probe_after_change=allow_probe_after_change,
    )
    if blocked:
        return False, "recovery-circuit-open", failures

    latest = latest_completed(runs)
    latest_time = completed_at(latest)
    if (
        not allow_probe_after_change
        and latest
        and latest.get("conclusion") in REAL_FAILURES
        and latest_time
        and now - latest_time < timedelta(hours=3)
    ):
        return False, "recovery-recent-failure-backoff", failures
    return True, "recovery-available", failures


def source_map(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(src.get("name")): src
        for src in (report.get("sources") or [])
        if isinstance(src, dict) and src.get("name")
    }


def detect_source_anomalies(
    current: dict[str, Any], previous: dict[str, Any] | None
) -> list[dict[str, Any]]:
    """Conservative drift detector.

    A source is flagged immediately for incomplete traversal/access errors.
    Volume drops are flagged only with a meaningful historical population so small,
    naturally sparse boards do not create noise.
    """
    anomalies: list[dict[str, Any]] = []
    curr = source_map(current)
    prev = source_map(previous or {})

    for name, src in curr.items():
        access_errors = int(src.get("accessErrors") or 0)
        if src.get("coverageComplete") is False or access_errors > 0:
            anomalies.append(
                {
                    "source": name,
                    "kind": "coverage",
                    "coverageComplete": src.get("coverageComplete"),
                    "accessErrors": access_errors,
                }
            )
            continue

        if name not in prev:
            continue
        cur_count = int(src.get("officialIdCount") or 0)
        prev_count = int(prev[name].get("officialIdCount") or 0)
        if prev_count >= 5 and cur_count == 0:
            anomalies.append(
                {"source": name, "kind": "zero", "previous": prev_count, "current": cur_count}
            )
        elif prev_count >= 20 and cur_count <= max(2, int(prev_count * 0.25)):
            anomalies.append(
                {
                    "source": name,
                    "kind": "drop",
                    "previous": prev_count,
                    "current": cur_count,
                    "ratio": round(cur_count / prev_count, 3) if prev_count else 0,
                }
            )
    return anomalies


def run_text(args: list[str], *, check: bool = False) -> str:
    proc = subprocess.run(args, text=True, capture_output=True)
    if check and proc.returncode != 0:
        raise RuntimeError(f"{' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def gh_runs(repo: str, filename: str) -> list[dict[str, Any]]:
    allowed = PRODUCTION_EVENTS[filename]
    found: dict[int, dict[str, Any]] = {}
    for event in sorted(allowed):
        raw = run_text(
            [
                "gh",
                "api",
                f"/repos/{repo}/actions/workflows/{filename}/runs?branch=main&event={event}&per_page=30",
            ],
            check=True,
        )
        try:
            runs = (json.loads(raw) or {}).get("workflow_runs", []) or []
        except Exception:
            runs = []
        for run in runs:
            try:
                found[int(run.get("id"))] = run
            except Exception:
                continue
    return production_runs(filename, list(found.values()))


def gh_active_target_keys(repo: str) -> set[str]:
    """Read one repository-wide active-run snapshot as a dispatch safety backstop."""
    raw = run_text(
        [
            "gh",
            "api",
            f"/repos/{repo}/actions/runs?per_page=100",
        ],
        check=True,
    )
    payload = json.loads(raw) or {}
    runs = payload.get("workflow_runs", []) or []
    by_path = {
        f".github/workflows/{filename}": key
        for key, filename in TARGETS.items()
    }
    active: set[str] = set()
    for run in runs:
        key = by_path.get(str(run.get("path") or ""))
        if not key:
            continue
        filename = TARGETS[key]
        if (
            run.get("status") in ACTIVE_STATES
            and run.get("event") in PRODUCTION_EVENTS[filename]
            and run.get("head_branch") == "main"
        ):
            active.add(key)
    return active


def git_commit_time(path: str) -> datetime | None:
    raw = run_text(["git", "log", "-1", "--format=%ct", "--", path])
    try:
        return datetime.fromtimestamp(int(raw), tz=timezone.utc).astimezone(KST)
    except Exception:
        return None


def git_change_count_after(since: datetime | None, paths: list[str]) -> int:
    if since is None:
        return 0
    raw = run_text(
        [
            "git",
            "log",
            "--format=%H",
            f"--since={since.astimezone(timezone.utc).isoformat()}",
            "--",
            *paths,
        ]
    )
    return len([line for line in raw.splitlines() if line.strip()])


def change_after_failure(change_at: datetime | None, failure_at: datetime | None) -> bool:
    """Allow a controlled probe only when the recovery contract changed after its last real failure."""
    return bool(change_at and failure_at and change_at > failure_at)


def unified_publication_stale(
    input_time: datetime | None, unified_time: datetime | None
) -> bool:
    """Return True when the user-facing unified publication lags verified input data."""
    return bool(input_time and (unified_time is None or input_time > unified_time))


def official_publication_lag(
    now: datetime,
    jobs_time: datetime | None,
    unified_time: datetime | None,
    *,
    threshold: timedelta = timedelta(hours=3),
) -> bool:
    if jobs_time is None:
        return False
    if unified_time is not None and unified_time >= jobs_time:
        return False
    return now - jobs_time > threshold


def private_refresh_due(
    last_refresh: datetime | None, now: datetime, max_age_hours: int
) -> bool:
    if last_refresh is None:
        return True
    return now - last_refresh > timedelta(hours=max_age_hours)


def choose_private_refresh_action(
    *,
    now: datetime,
    all_runs: dict[str, list[dict[str, Any]]],
    private_refresh_times: dict[str, datetime | None],
    private_freshness: dict[str, dict[str, Any]],
    active_private: list[str],
) -> tuple[str | None, str | None]:
    """Choose one guarded private refresh without weakening official fail-closed gates."""
    if active_private:
        return (
            "skip-private-active",
            "active private refresh workflows: " + ",".join(active_private),
        )

    candidate_time = git_commit_time("artmore_reconciliation_report.candidate.json")
    canonical_artmore_time = git_commit_time("artmore_reconciliation_report.json")
    candidate_report = load_json("artmore_reconciliation_report.candidate.json", {})
    artmore_ready = bool(
        candidate_time
        and (canonical_artmore_time is None or candidate_time > canonical_artmore_time)
        and candidate_report.get("healthy") is True
        and candidate_report.get("traversalComplete") is True
        and int(candidate_report.get("missingAfterCount") or 0) == 0
    )

    private_candidates: list[tuple[float, str]] = []
    if artmore_ready:
        private_candidates.append((10_000.0, ARTMORE_PROMOTE_KEY))
    for key, spec in PRIVATE_REFRESH_TARGETS.items():
        refreshed_at = private_refresh_times.get(key)
        if not private_refresh_due(refreshed_at, now, int(spec["maxAgeHours"])):
            continue
        age_hours = (
            (now - refreshed_at).total_seconds() / 3600
            if refreshed_at is not None
            else 10_000.0
        )
        private_candidates.append(
            (age_hours / float(spec["maxAgeHours"]), key)
        )

    skipped_private: list[str] = []
    for _, key in sorted(private_candidates, reverse=True):
        runs = all_runs[key]
        blocked, failures, _ = circuit_blocked(key, runs, now)
        latest = latest_completed(runs)
        latest_time = completed_at(latest)
        recent_failure = bool(
            latest
            and latest.get("conclusion") in REAL_FAILURES
            and latest_time
            and now - latest_time < timedelta(hours=1)
        )
        if blocked or recent_failure:
            skipped_private.append(
                f"{key}:{'circuit' if blocked else 'backoff'}:{failures}"
            )
            continue
        if key == ARTMORE_PROMOTE_KEY:
            return (
                key,
                "verified ArtMore candidate is newer than canonical publication",
            )
        freshness = private_freshness[key]
        return (
            key,
            (
                f"private source refresh overdue: {key}, "
                f"ageHours={freshness['ageHours']}, "
                f"maxAgeHours={freshness['maxAgeHours']}"
            ),
        )

    if private_candidates and skipped_private:
        return (
            "skip-private-backoff",
            "private refreshes are temporarily backed off: " + ",".join(skipped_private),
        )
    return None, None


def previous_reconciliation_report() -> dict[str, Any] | None:
    commits = [
        x.strip()
        for x in run_text(
            ["git", "log", "--format=%H", "-2", "--", "source_reconciliation_report.json"]
        ).splitlines()
        if x.strip()
    ]
    if len(commits) < 2:
        return None
    raw = run_text(["git", "show", f"{commits[1]}:source_reconciliation_report.json"])
    try:
        return json.loads(raw)
    except Exception:
        return None


def compute_state(now: datetime, repo: str) -> dict[str, Any]:
    all_runs = {key: gh_runs(repo, filename) for key, filename in TARGETS.items()}
    watchdog_runs = gh_runs(repo, WATCHDOG_WORKFLOW)
    previous_watchdog = latest_completed(watchdog_runs)
    previous_watchdog_at = completed_at(previous_watchdog)
    watchdog_lag = watchdog_schedule_lag(previous_watchdog_at, now)
    watchdog_previous_age_hours = (
        round((now - previous_watchdog_at).total_seconds() / 3600, 2)
        if previous_watchdog_at is not None
        else None
    )

    active_snapshot = gh_active_target_keys(repo)
    active = [
        key
        for key in CORE_TARGETS
        if key in active_snapshot
        or any(r.get("status") in ACTIVE_STATES for r in all_runs[key])
    ]
    active_private = [
        key
        for key in (*PRIVATE_REFRESH_TARGETS.keys(), ARTMORE_PROMOTE_KEY)
        if key in active_snapshot
        or any(r.get("status") in ACTIVE_STATES for r in all_runs[key])
    ]

    root = load_json("collector_status.json", {})
    fast = root.get("fast", {}) if isinstance(root, dict) else {}
    success_at = parse_time(fast.get("lastSuccessAt"))
    updated_at = parse_time(fast.get("updatedAt"))
    success_age = now - success_at if success_at else None
    running_age = now - updated_at if updated_at else None
    state = str(fast.get("state") or "")
    production_success_at, production_success_path = latest_verified_production_success(root)
    production_success_age = (
        now - production_success_at if production_success_at is not None else None
    )

    registry = load_json("sources.json", {})
    jobs_payload = load_json("jobs.json", {})
    required_registry, registry_details = registry_contract_status(registry, jobs_payload)

    validation_paths = [
        "sources.json",
        ".github/workflows/update-jobs.yml",
        "scripts/scrape_jobs.py",
        "scripts/repair_gyeonggi_support.py",
        "scripts/resolve_support_links.py",
        "scripts/enrich_support_periods.py",
        "scripts/enrich_seoul_get_fallback.py",
        "scripts/recover_seoul_office_cms_jobs.py",
        "scripts/verify_jobs.py",
        "scripts/merge_recovery_snapshot.py",
        "scripts/validate_reconciliation_policy.py",
        "scripts/validate_reconciliation_policy_v3.py",
        "scripts/reconcile_source_ids.py",
        "scripts/verify_required_regions.py",
        "scripts/merge_incheon_official.py",
        "scripts/ensure_incheon_registry.py",
        "scripts/stable_source_identity.py",
        "scripts/source_registry.py",
    ]
    collector_changes_after_success = git_change_count_after(success_at, validation_paths)
    _, fast_failure_time = consecutive_real_failures(all_runs["fast"])
    collector_contract_changed_after_failure = (
        git_change_count_after(fast_failure_time, validation_paths) > 0
        if fast_failure_time is not None
        else False
    )

    unified_validation_paths = [
        ".github/workflows/unified-search.yml",
        "scripts/build_unified_search.py",
        "scripts/build_unified_search_multi.py",
        "scripts/validate_unified_search.py",
        "scripts/validate_unified_search_multi.py",
        "scripts/validate_required_metro_publication.py",
        "scripts/crosscheck_private_official.py",
        "scripts/reconcile_cultural_foundation_coverage.py",
        "scripts/source_registry.py",
        "scripts/private_source_registry.py",
        "scripts/direct_post_links.py",
        "scripts/audit_direct_post_links.py",
        "scripts/apply_unified_frontend.py",
        "scripts/crawl_seekle_instructor_jobs.py",
        "scripts/crawl_boramyc_instructor_jobs.py",
        "scripts/publication_transaction.py",
        "verified_foundation_official_sources.json",
        "official_foundation_jobs.json",
    ]
    _, unified_failure_time = consecutive_real_failures(all_runs["unified"])
    unified_contract_changed_after_failure = (
        git_change_count_after(unified_failure_time, unified_validation_paths) > 0
        if unified_failure_time is not None
        else False
    )

    jobs_time = git_commit_time("jobs.json")
    unified_time = git_commit_time("unified_jobs.json")
    private_report_times = {
        key: git_commit_time(str(spec["report"]))
        for key, spec in PRIVATE_REFRESH_TARGETS.items()
    }
    private_workflow_success_times = {
        key: completed_at(latest_success(all_runs[key]))
        for key in PRIVATE_REFRESH_TARGETS
    }
    private_refresh_times = {
        key: max(
            (
                value
                for value in (
                    private_report_times.get(key),
                    private_workflow_success_times.get(key),
                )
                if value is not None
            ),
            default=None,
        )
        for key in PRIVATE_REFRESH_TARGETS
    }
    publication_input_times = [jobs_time, *private_report_times.values()]
    latest_publication_input = max(
        (value for value in publication_input_times if value is not None),
        default=None,
    )
    private_freshness = {}
    for key, spec in PRIVATE_REFRESH_TARGETS.items():
        refreshed_at = private_refresh_times.get(key)
        age_hours = (
            round((now - refreshed_at).total_seconds() / 3600, 2)
            if refreshed_at is not None
            else None
        )
        private_freshness[key] = {
            "workflow": spec["workflow"],
            "report": spec["report"],
            "reportCommitAt": (
                private_report_times.get(key).isoformat()
                if private_report_times.get(key)
                else None
            ),
            "lastWorkflowSuccessAt": (
                private_workflow_success_times.get(key).isoformat()
                if private_workflow_success_times.get(key)
                else None
            ),
            "lastRefreshAt": refreshed_at.isoformat() if refreshed_at else None,
            "ageHours": age_hours,
            "maxAgeHours": spec["maxAgeHours"],
            "overdue": private_refresh_due(refreshed_at, now, int(spec["maxAgeHours"])),
        }

    current_reconciliation = load_json("source_reconciliation_report.json", {})
    anomalies = detect_source_anomalies(
        current_reconciliation, previous_reconciliation_report()
    )

    failure_state: dict[str, dict[str, Any]] = {}
    for key, runs in all_runs.items():
        failures, latest_failure = consecutive_real_failures(runs)
        failure_state[key] = {
            "consecutiveRealFailures": failures,
            "latestRealFailureAt": latest_failure.isoformat() if latest_failure else None,
        }

    recovery_workflow_time = git_commit_time(".github/workflows/recover-missing-jobs.yml")
    _, recovery_failure_time = consecutive_real_failures(all_runs["recovery"])
    recovery_contract_changed_after_failure = change_after_failure(
        recovery_workflow_time, recovery_failure_time
    )

    action = "skip-healthy"
    reason = "all production contracts current"
    circuit = None

    if active:
        action = "skip-active-run"
        reason = "active workflows: " + ",".join(active)
        # Fast writes the canonical official artifacts, while private refresh writers
        # update isolated source reports. Allow exactly one overdue private writer to
        # use this otherwise blocked watchdog slot; active_private still serializes
        # private refreshes and all source-specific circuit/backoff rules remain intact.
        if set(active) == {"fast"}:
            # A completed private refresh can safely rebuild Unified from the last
            # verified official dataset while the next Fast crawl continues. Publish
            # that user-visible delta before launching another private collector.
            if unified_publication_stale(latest_publication_input, unified_time):
                unified_runs = all_runs["unified"]
                blocked_unified, unified_failures, _ = circuit_blocked(
                    "unified",
                    unified_runs,
                    now,
                    allow_probe_after_change=unified_contract_changed_after_failure,
                )
                latest_unified = latest_completed(unified_runs)
                latest_unified_time = completed_at(latest_unified)
                recent_unified_failure = bool(
                    not unified_contract_changed_after_failure
                    and latest_unified
                    and latest_unified.get("conclusion") in REAL_FAILURES
                    and latest_unified_time
                    and now - latest_unified_time < timedelta(hours=1)
                )
                if not blocked_unified and not recent_unified_failure:
                    action = "unified"
                    reason = (
                        "publish newer verified private input while Fast remains active: "
                        f"latestInput={latest_publication_input}, unified={unified_time}"
                    )
                else:
                    reason += (
                        "; Unified publication temporarily blocked while Fast is active: "
                        f"circuit={blocked_unified}, failures={unified_failures}, "
                        f"recentFailure={recent_unified_failure}"
                    )

            if action == "skip-active-run":
                private_action, private_reason = choose_private_refresh_action(
                    now=now,
                    all_runs=all_runs,
                    private_refresh_times=private_refresh_times,
                    private_freshness=private_freshness,
                    active_private=active_private,
                )
                if private_action and private_action.startswith("private-"):
                    action = private_action
                    reason = (
                        "Fast refresh is already active; using one isolated private refresh slot. "
                        + str(private_reason or "")
                    )
                elif private_reason:
                    reason += "; " + private_reason
    else:
        fast_needed = (
            not required_registry
            or success_at is None
            or success_age > FAST_REFRESH_AFTER
            or collector_changes_after_success > 0
        )
        fast_status_running = (
            state == "running"
            and running_age is not None
            and running_age <= timedelta(minutes=90)
        )
        unified_runs = all_runs["unified"]
        latest_unified = latest_completed(unified_runs)

        # If verified official jobs have already advanced beyond the user-facing
        # unified dataset, drain that publication backlog before starting another
        # potentially long Fast refresh. Unified publication remains fail-closed.
        if unified_publication_stale(jobs_time, unified_time) and not fast_status_running:
            blocked, failures, _ = circuit_blocked(
                "unified",
                unified_runs,
                now,
                allow_probe_after_change=unified_contract_changed_after_failure,
            )
            latest_unified_time = completed_at(latest_unified)
            if blocked:
                action = "skip-unified-circuit-open"
                circuit = "unified"
                reason = f"Unified search circuit open after {failures} real failures"
            elif (
                not unified_contract_changed_after_failure
                and latest_unified
                and latest_unified.get("conclusion") in REAL_FAILURES
                and latest_unified_time
                and now - latest_unified_time < timedelta(hours=1)
            ):
                action = "skip-unified-backoff"
                reason = "unified search failed within the last hour"
            else:
                action = "unified"
                reason = (
                    "publish verified official jobs backlog before another Fast refresh: "
                    f"jobs={jobs_time}, unified={unified_time}"
                )

            # A blocked Unified publication must not starve official collection.
            # If Fast itself is due, let its independent circuit/backoff decide.
            if action in {"skip-unified-circuit-open", "skip-unified-backoff"} and fast_needed:
                blocked_fast, fast_failures_now, fast_latest_failure = circuit_blocked(
                    "fast",
                    all_runs["fast"],
                    now,
                    allow_probe_after_change=collector_contract_changed_after_failure,
                )
                if blocked_fast:
                    production_stale_for_p0 = (
                        production_success_age is None
                        or production_success_age > P0_STALE_AFTER
                    )
                    recovery_available = False
                    recovery_gate = "production-not-p0-stale"
                    recovery_failures = 0
                    if production_stale_for_p0:
                        recovery_available, recovery_gate, recovery_failures = recovery_fallback_available(
                            all_runs["recovery"],
                            now,
                            allow_probe_after_change=recovery_contract_changed_after_failure,
                        )
                    if recovery_available:
                        action = "recovery"
                        circuit = None
                        reason = (
                            f"Unified is blocked and Fast circuit is open after {fast_failures_now} real failures; "
                            "use Recovery as alternative verified production path"
                        )
                    else:
                        action = "skip-fast-circuit-open"
                        circuit = "fast"
                        reason = (
                            f"Unified is blocked; Fast circuit open after {fast_failures_now} real failures; "
                            f"lastFastFailure={fast_latest_failure.isoformat() if fast_latest_failure else None}; "
                            f"recoveryFallback={recovery_gate}; recoveryFailures={recovery_failures}"
                        )
                else:
                    latest_fast = latest_completed(all_runs["fast"])
                    latest_fast_time = completed_at(latest_fast)
                    if (
                        not collector_contract_changed_after_failure
                        and latest_fast
                        and latest_fast.get("conclusion") in REAL_FAILURES
                        and latest_fast_time
                        and now - latest_fast_time < timedelta(hours=1)
                    ):
                        action = "skip-fast-backoff"
                        circuit = None
                        reason = "Unified is blocked; Fast refresh failed within the last hour"
                    else:
                        action = "fast"
                        circuit = None
                        reason = (
                            "Unified is blocked but official collection is due; "
                            f"successAgeHours={round(success_age.total_seconds()/3600, 2) if success_age else None}, "
                            f"collectorContractChangedAfterFailure={collector_contract_changed_after_failure}"
                        )
        elif fast_needed and not fast_status_running:
            blocked, failures, latest_failure = circuit_blocked(
                "fast",
                all_runs["fast"],
                now,
                allow_probe_after_change=collector_contract_changed_after_failure,
            )
            if blocked:
                production_stale_for_p0 = (
                    production_success_age is None
                    or production_success_age > P0_STALE_AFTER
                )
                recovery_available = False
                recovery_gate = "production-not-p0-stale"
                recovery_failures = 0
                if production_stale_for_p0:
                    recovery_available, recovery_gate, recovery_failures = recovery_fallback_available(
                        all_runs["recovery"],
                        now,
                        allow_probe_after_change=recovery_contract_changed_after_failure,
                    )

                if recovery_available:
                    action = "recovery"
                    reason = (
                        f"Fast circuit open after {failures} real failures; "
                        "use Recovery as alternative verified production path on a fresh runner; "
                        f"lastFastFailure={latest_failure.isoformat() if latest_failure else None}"
                    )
                else:
                    action = "skip-fast-circuit-open"
                    circuit = "fast"
                    reason = (
                        f"Fast circuit open after {failures} real failures; "
                        f"last failure={latest_failure.isoformat() if latest_failure else None}; "
                        f"recoveryFallback={recovery_gate}; "
                        f"recoveryFailures={recovery_failures}"
                    )
            else:
                latest_fast = latest_completed(all_runs["fast"])
                latest_fast_time = completed_at(latest_fast)
                if (
                    not collector_contract_changed_after_failure
                    and latest_fast
                    and latest_fast.get("conclusion") in REAL_FAILURES
                    and latest_fast_time
                    and now - latest_fast_time < timedelta(hours=1)
                ):
                    action = "skip-fast-backoff"
                    reason = "fast refresh failed within the last hour"
                else:
                    action = "fast"
                    reason = (
                        f"registryComplete={required_registry}, "
                        f"successAgeHours={round(success_age.total_seconds()/3600, 2) if success_age else None}, "
                        f"collectorChangesAfterSuccess={collector_changes_after_success}, "
                        f"collectorContractChangedAfterFailure={collector_contract_changed_after_failure}"
                    )
        elif fast_status_running:
            action = "skip-status-running"
            reason = "collector_status reports a recent running Fast job"
        else:
            audit_runs = all_runs["completeness"]
            recovery_runs = all_runs["recovery"]
            latest_audit = latest_completed(audit_runs)
            latest_audit_success = latest_success(audit_runs)
            latest_recovery = latest_completed(recovery_runs)
            latest_recovery_success = latest_success(recovery_runs)

            audit_success_time = completed_at(latest_audit_success)
            audit_current = bool(
                audit_success_time
                and audit_success_time.date() == now.date()
                and (jobs_time is None or audit_success_time >= jobs_time)
            )
            audit_failed = bool(
                latest_audit and latest_audit.get("conclusion") in REAL_FAILURES
            )
            audit_failure_time = completed_at(latest_audit) if audit_failed else None
            recovery_success_time = completed_at(latest_recovery_success)
            recovery_latest_time = completed_at(latest_recovery)

            # User-visible publication must not wait behind long recovery/completeness
            # loops once jobs.json has already passed the Fast publication gates.
            # unified-search has its own fail-closed validation, so a failed rebuild
            # preserves the last-known-good unified_jobs.json.
            if unified_publication_stale(latest_publication_input, unified_time):
                blocked, failures, _ = circuit_blocked(
                    "unified",
                    unified_runs,
                    now,
                    allow_probe_after_change=unified_contract_changed_after_failure,
                )
                latest_unified_time = completed_at(latest_unified)
                if blocked:
                    action = "skip-unified-circuit-open"
                    circuit = "unified"
                    reason = f"Unified search circuit open after {failures} real failures"
                elif (
                    not unified_contract_changed_after_failure
                    and latest_unified
                    and latest_unified.get("conclusion") in REAL_FAILURES
                    and latest_unified_time
                    and now - latest_unified_time < timedelta(hours=1)
                ):
                    action = "skip-unified-backoff"
                    reason = "unified search failed within the last hour"
                else:
                    action = "unified"
                    reason = (
                        "verified publication input is newer than unified_jobs.json: "
                        f"latestInput={latest_publication_input}, jobs={jobs_time}, "
                        f"unified={unified_time}"
                    )
            elif audit_failed:
                if (
                    recovery_success_time
                    and audit_failure_time
                    and recovery_success_time > audit_failure_time
                ):
                    blocked, failures, _ = circuit_blocked(
                        "completeness", audit_runs, now
                    )
                    if blocked:
                        action = "skip-completeness-circuit-open"
                        circuit = "completeness"
                        reason = f"Completeness circuit open after {failures} real failures"
                    else:
                        action = "completeness"
                        reason = (
                            "successful recovery occurred after failed completeness audit; "
                            "re-prove production"
                        )
                else:
                    blocked, failures, _ = circuit_blocked(
                        "recovery",
                        recovery_runs,
                        now,
                        allow_probe_after_change=recovery_contract_changed_after_failure,
                    )
                    if blocked:
                        action = "skip-recovery-circuit-open"
                        circuit = "recovery"
                        reason = f"Recovery circuit open after {failures} real failures"
                    elif (
                        not recovery_contract_changed_after_failure
                        and latest_recovery
                        and latest_recovery.get("conclusion") in REAL_FAILURES
                        and recovery_latest_time
                        and audit_failure_time
                        and recovery_latest_time > audit_failure_time
                        and now - recovery_latest_time < timedelta(hours=3)
                    ):
                        action = "skip-recovery-backoff"
                        reason = "recovery failed recently; three-hour backoff active"
                    else:
                        action = "recovery"
                        if recovery_contract_changed_after_failure:
                            reason = (
                                "recovery contract changed after the latest real failure; "
                                "allow one controlled probe"
                            )
                        else:
                            reason = (
                                "latest official completeness audit failed without a newer "
                                "successful recovery"
                            )
            elif not audit_current and now.hour >= 2:
                blocked, failures, _ = circuit_blocked(
                    "completeness", audit_runs, now
                )
                if blocked:
                    action = "skip-completeness-circuit-open"
                    circuit = "completeness"
                    reason = f"Completeness circuit open after {failures} real failures"
                else:
                    action = "completeness"
                    reason = "no current successful daily official completeness proof"

            # A blocked official proof/recovery cannot make stale private sources
            # wait indefinitely. Keep the official incident open while using this
            # otherwise idle watchdog slot for one separately guarded refresh.
            if action in PRIVATE_REFRESH_IDLE_ACTIONS:
                private_action, private_reason = choose_private_refresh_action(
                    now=now,
                    all_runs=all_runs,
                    private_refresh_times=private_refresh_times,
                    private_freshness=private_freshness,
                    active_private=active_private,
                )
                if private_action:
                    action = private_action
                    reason = private_reason or reason

    if action == "fast" and watchdog_lag:
        reason += (
            "; watchdog previous completed run is stale: "
            f"ageHours={watchdog_previous_age_hours}"
        )

    fast_failures = failure_state["fast"]["consecutiveRealFailures"]
    stale_hours = (
        round(success_age.total_seconds() / 3600, 2) if success_age is not None else None
    )
    production_stale_hours = (
        round(production_success_age.total_seconds() / 3600, 2)
        if production_success_age is not None
        else None
    )
    p0_reasons: list[str] = []
    if not required_registry:
        p0_reasons.append("registry-contract-incomplete")
    if production_success_at is None:
        p0_reasons.append("no-verified-production-success")
    elif production_success_age is not None and production_success_age > P0_STALE_AFTER:
        p0_reasons.append("verified-production-stale>6h")
    if circuit == "fast" and (
        production_success_age is None or production_success_age > P0_STALE_AFTER
    ):
        p0_reasons.append("fast-circuit-open-without-fresh-alternative")
    if official_publication_lag(now, jobs_time, unified_time):
        p0_reasons.append("official-publication-lag>3h")
    p0_incident = bool(p0_reasons)

    workflow_count = len(list(Path(".github/workflows").glob("*.yml"))) + len(
        list(Path(".github/workflows").glob("*.yaml"))
    )

    return {
        "generatedAt": now.isoformat(),
        "action": action,
        "reason": reason,
        "requiredRegistryComplete": required_registry,
        "registryDetails": registry_details,
        "fastState": state,
        "fastLastSuccessAt": fast.get("lastSuccessAt"),
        "fastSuccessAgeHours": stale_hours,
        "fastRefreshAfterHours": round(FAST_REFRESH_AFTER.total_seconds() / 3600, 2),
        "p0StaleAfterHours": round(P0_STALE_AFTER.total_seconds() / 3600, 2),
        "productionLastVerifiedAt": (
            production_success_at.isoformat() if production_success_at else None
        ),
        "productionVerifiedBy": production_success_path,
        "productionVerifiedAgeHours": production_stale_hours,
        "watchdogPreviousCompletedAt": (
            previous_watchdog_at.isoformat() if previous_watchdog_at else None
        ),
        "watchdogPreviousCompletedAgeHours": watchdog_previous_age_hours,
        "watchdogScheduleLag": watchdog_lag,
        "collectorChangesAfterSuccess": collector_changes_after_success,
        "collectorContractChangedAfterFailure": collector_contract_changed_after_failure,
        "unifiedContractChangedAfterFailure": unified_contract_changed_after_failure,
        "recoveryWorkflowCommitAt": recovery_workflow_time.isoformat() if recovery_workflow_time else None,
        "recoveryContractChangedAfterFailure": recovery_contract_changed_after_failure,
        "activeTargets": active,
        "activePrivateTargets": active_private,
        "privateFreshness": private_freshness,
        "latestPublicationInputAt": latest_publication_input.isoformat() if latest_publication_input else None,
        "circuit": circuit,
        "failureState": failure_state,
        "sourceAnomalies": anomalies,
        "p0Incident": p0_incident,
        "p0Reasons": p0_reasons,
        "jobsCommitAt": jobs_time.isoformat() if jobs_time else None,
        "unifiedCommitAt": unified_time.isoformat() if unified_time else None,
        "workflowCount": workflow_count,
        "priority": ["fast", "unified", "recovery", "completeness", "private-refresh"],
        "fastFailures": fast_failures,
    }


def gh_json(repo: str, method: str, path: str, fields: dict[str, str] | None = None) -> Any:
    cmd = ["gh", "api", "--method", method, f"/repos/{repo}/{path}"]
    for key, value in (fields or {}).items():
        cmd += ["-f", f"{key}={value}"]
    raw = run_text(cmd, check=True)
    return json.loads(raw) if raw else None


def list_recent_issues(repo: str) -> list[dict[str, Any]]:
    raw = run_text(
        [
            "gh",
            "api",
            f"/repos/{repo}/issues?state=all&per_page=100&sort=created&direction=desc",
        ],
        check=True,
    )
    try:
        return [
            x for x in json.loads(raw) if isinstance(x, dict) and "pull_request" not in x
        ]
    except Exception:
        return []


def find_issue(issues: list[dict[str, Any]], title: str, *, open_only: bool = False) -> dict[str, Any] | None:
    for issue in issues:
        if issue.get("title") != title:
            continue
        if open_only and issue.get("state") != "open":
            continue
        return issue
    return None


def create_issue(repo: str, title: str, body: str) -> int:
    result = gh_json(repo, "POST", "issues", {"title": title, "body": body})
    return int(result["number"])


def close_issue(repo: str, number: int, body: str | None = None) -> None:
    if body:
        gh_json(repo, "POST", f"issues/{number}/comments", {"body": body})
    gh_json(
        repo,
        "PATCH",
        f"issues/{number}",
        {"state": "closed", "state_reason": "completed"},
    )


def manage_issues(repo: str, state: dict[str, Any], now: datetime) -> None:
    issues = list_recent_issues(repo)

    p0 = find_issue(issues, P0_TITLE, open_only=True)
    if state["p0Incident"]:
        if p0 is None:
            body = (
                "Automated production incident opened by the single operations watchdog.\n\n"
                f"- generatedAt: `{state['generatedAt']}`\n"
                f"- action: `{state['action']}`\n"
                f"- reason: {state['reason']}\n"
                f"- registryComplete: `{state['requiredRegistryComplete']}`\n"
                f"- registryDetails: `{json.dumps(state.get('registryDetails') or {}, ensure_ascii=False)}`\n"
                f"- fastLastSuccessAt: `{state['fastLastSuccessAt']}`\n"
                f"- fastSuccessAgeHours: `{state['fastSuccessAgeHours']}`\n"
                f"- productionLastVerifiedAt: `{state.get('productionLastVerifiedAt')}`\n"
                f"- productionVerifiedBy: `{state.get('productionVerifiedBy')}`\n"
                f"- productionVerifiedAgeHours: `{state.get('productionVerifiedAgeHours')}`\n"
                f"- watchdogPreviousCompletedAt: `{state.get('watchdogPreviousCompletedAt')}`\n"
                f"- watchdogPreviousCompletedAgeHours: `{state.get('watchdogPreviousCompletedAgeHours')}`\n"
                f"- watchdogScheduleLag: `{state.get('watchdogScheduleLag')}`\n"
                f"- p0Reasons: `{json.dumps(state.get('p0Reasons') or [], ensure_ascii=False)}`\n"
                f"- fastConsecutiveRealFailures: `{state['fastFailures']}`\n\n"
                "The watchdog keeps last-known-good production data in place. "
                "Automatic retries are circuit-broken after repeated real failures; "
                "a controlled probe resumes after the backoff window or after collector code changes."
            )
            create_issue(repo, P0_TITLE, body)
    elif p0 is not None:
        close_issue(
            repo,
            int(p0["number"]),
            "Production freshness/registry conditions recovered; automated incident closed.",
        )

    p1 = find_issue(issues, P1_TITLE, open_only=True)
    anomalies = state.get("sourceAnomalies") or []
    if anomalies:
        if p1 is None:
            lines = "\n".join(
                f"- `{a.get('source')}`: {json.dumps(a, ensure_ascii=False)}"
                for a in anomalies[:20]
            )
            body = (
                "Conservative source-drift detector found a meaningful source-level anomaly.\n\n"
                f"{lines}\n\n"
                "This is an early-warning signal, not proof of a confirmed user-visible omission. "
                "The completeness audit and independent official-posting comparison remain authoritative."
            )
            create_issue(repo, P1_TITLE, body)
    elif p1 is not None:
        close_issue(
            repo,
            int(p1["number"]),
            "Source reconciliation returned to its normal range; automated anomaly incident closed.",
        )

    if now.weekday() == 0 and now.hour >= 9:
        iso = now.isocalendar()
        title = f"[AUTO][WEEKLY] {iso.year}-W{iso.week:02d} operations heartbeat"
        if find_issue(issues, title) is None:
            failures = state.get("failureState") or {}
            body = (
                "Automated weekly operations heartbeat.\n\n"
                f"- generatedAt: `{state['generatedAt']}`\n"
                f"- production action now: `{state['action']}`\n"
                f"- required registry complete: `{state['requiredRegistryComplete']}`\n"
                f"- fast last success: `{state['fastLastSuccessAt']}`\n"
                f"- fast age hours: `{state['fastSuccessAgeHours']}`\n"
                f"- verified production: `{state.get('productionVerifiedBy')}` at `{state.get('productionLastVerifiedAt')}` (ageHours=`{state.get('productionVerifiedAgeHours')}`)\n"
                f"- watchdog schedule lag: `{state.get('watchdogScheduleLag')}` (previousCompletedAgeHours=`{state.get('watchdogPreviousCompletedAgeHours')}`)\n"
                f"- source anomalies: `{len(state.get('sourceAnomalies') or [])}`\n"
                f"- workflow files: `{state['workflowCount']}`\n"
                f"- failure counters: `{json.dumps(failures, ensure_ascii=False)}`\n\n"
                "This issue is a heartbeat record only; healthy heartbeat issues close automatically."
            )
            number = create_issue(repo, title, body)
            close_issue(repo, number)


def write_outputs(state: dict[str, Any], github_output: str | None) -> None:
    if not github_output:
        return
    with open(github_output, "a", encoding="utf-8") as fh:
        fh.write(f"action={state['action']}\n")
        fh.write(f"p0_incident={'true' if state['p0Incident'] else 'false'}\n")
        fh.write(f"source_anomalies={len(state.get('sourceAnomalies') or [])}\n")
        fh.write(f"circuit={state.get('circuit') or ''}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--github-output")
    parser.add_argument("--state-file", default="/tmp/production-supervisor.json")
    parser.add_argument("--manage-issues", action="store_true")
    args = parser.parse_args()

    if not args.repo:
        raise SystemExit("repository is required via --repo or GITHUB_REPOSITORY")

    now = datetime.now(KST)
    state = compute_state(now, args.repo)
    Path(args.state_file).write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_outputs(state, args.github_output)

    if args.manage_issues:
        manage_issues(args.repo, state, now)

    print(json.dumps(state, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
