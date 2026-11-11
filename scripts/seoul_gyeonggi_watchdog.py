#!/usr/bin/env python3
"""Read-only regional dispatch decision in the existing approved watchdog.

Holding Incheon means automatic Fast/recovery/completeness jobs must not retry
its broken boards. Only an independently verified regional writer is chosen
when due, with an active-run guard and a 6-hour failure backoff.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

REGIONAL_ACTION = "seoul-gyeonggi"
BLOCKED_ICE_ACTIONS = {"fast", "recovery", "completeness"}
ACTIVE = {"queued", "in_progress", "waiting", "requested", "pending"}
FAILED = {"failure", "timed_out", "startup_failure"}


def parse_time(raw):
    if not raw:
        return None
    try:
        value = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        return value if value.tzinfo else None
    except (ValueError, TypeError):
        return None


REGIONAL_POLICY = "seoul-gyeonggi-isolated-verified-v1"
# Start a verified refresh before the 6-hour user-facing staleness boundary.
# A full 90-day regional traversal typically takes about an hour; keep a
# two-hour margin for collection, independent checks, Unified and Pages.
REGIONAL_REFRESH_AFTER = timedelta(hours=4)
# Only an already vetted private-source dispatch key from the same supervisor
# execution may fill an idle gap while verified regional data is fresh, or
# during regional failure backoff when the last verified snapshot is published.
ALLOWED_PRIVATE_FALLBACK = {
    "private-lessoninfo", "private-lessoninfo-links", "private-jobteacher",
    "private-artmore-candidate", "private-artmore-promote",
    "private-gonggonggangsa", "private-cleaneye", "private-seekle",
    "private-boramyc", "private-foundation",
}


def valid_private_fallback(supervisor_state, selected, now):
    if not isinstance(supervisor_state, dict):
        return None
    when = parse_time(supervisor_state.get("generatedAt"))
    if (when is None or when > now + timedelta(minutes=5) or
            now - when > timedelta(minutes=10) or
            supervisor_state.get("action") != selected or
            supervisor_state.get("activeTargets") or
            supervisor_state.get("activePrivateTargets")):
        return None
    chosen = supervisor_state.get("regionalPrivateFallbackAction")
    if chosen not in ALLOWED_PRIVATE_FALLBACK:
        return None
    freshness = (supervisor_state.get("privateFreshness") or {}).get(chosen)
    # ArtMore promotion is a special case: a recently verified candidate is
    # newer than canonical, rather than a stale source.
    if chosen != "private-artmore-promote" and not (
        isinstance(freshness, dict) and freshness.get("overdue") is True
    ):
        return None
    return chosen



def verified_snapshot(report, snapshot):
    """Require published 38-source bytes AND matching independent proof.

    A standalone report cannot mark the regional data fresh: Unified could
    otherwise remain stuck on October's canonical jobs indefinitely.
    """
    if not isinstance(report, dict) or not isinstance(snapshot, dict):
        return None
    meta = snapshot.get("regionalPublication") or {}
    if (report.get("state") != "verified" or
            report.get("policy") != REGIONAL_POLICY or
            meta.get("state") != "verified" or
            meta.get("policy") != REGIONAL_POLICY or
            report.get("generatedAt") != meta.get("generatedAt") or
            meta.get("refreshedRegions") != ["경기", "서울"] or
            int(meta.get("refreshedOfficialSourceCount") or 0) != 38 or
            int(snapshot.get("officialSourceCount") or 0) != 38 or
            (meta.get("heldRegions") or {}).get("인천", {}).get("state") != "stale" or
            set(snapshot.get("sources") or {}) != {"gyeonggi", "seoul"}):
        return None
    jobs = snapshot.get("jobs")
    if not isinstance(jobs, list) or len(jobs) < 100:
        return None
    counts = {"gyeonggi": 0, "seoul": 0}
    for job in jobs:
        if not isinstance(job, dict):
            return None
        province = job.get("province")
        if province == "경기":
            counts["gyeonggi"] += 1
        elif province == "서울":
            counts["seoul"] += 1
        else:
            return None
    if report.get("counts") != counts or meta.get("officialJobs") != counts:
        return None
    return parse_time(meta.get("generatedAt"))


def unified_has_snapshot(unified, snapshot):
    if not isinstance(unified, dict) or not isinstance(snapshot, dict):
        return False
    own = snapshot.get("regionalPublication") or {}
    published = unified.get("regionalPublication") or {}
    return (published.get("policy") == REGIONAL_POLICY and
            published.get("state") == "verified" and
            published.get("generatedAt") == own.get("generatedAt") and
            published.get("refreshedRegions") == ["경기", "서울"] and
            (published.get("heldRegions") or {}).get("인천", {}).get("state") == "stale" and
            isinstance(unified.get("jobs"), list) and len(unified["jobs"]) >= 100)


def unified_retry_gate(runs, snapshot_at, now):
    """Fail-closed against racing or endlessly repeating Unified publication.

    Decisions use *workflow_dispatch* production runs only, never PR checks.
    A successful Unified run after the snapshot that did not publish the region
    is an incident, not permission to blindly dispatch again.
    """
    if not isinstance(runs, list):
        return False, "Unified run history unavailable"
    relevant = [r for r in runs
                if isinstance(r, dict)
                and r.get("event") == "workflow_dispatch"
                and r.get("head_branch") == "main"]
    if any(r.get("status") in ACTIVE for r in relevant):
        return False, "Unified writer already active"
    finished = sorted(
        (r for r in relevant if r.get("status") == "completed"),
        key=lambda r: str(r.get("updated_at") or r.get("created_at") or ""),
        reverse=True,
    )
    failures = 0
    for run in finished:
        when = parse_time(run.get("updated_at") or run.get("created_at"))
        if when is None or when > now:
            continue
        age = now - when
        if run.get("conclusion") in FAILED:
            if age < timedelta(hours=1):
                return False, "recent Unified failure; one-hour backoff"
            if age < timedelta(hours=6):
                failures += 1
        if run.get("conclusion") == "success" and when >= snapshot_at:
            return False, "Unified completed after regional snapshot but display proof is missing"
    if failures >= 2:
        return False, "Unified failed twice within six hours; circuit open"
    return True, "Unified retry gate clear"


def decide(selected, report, runs, now, *, snapshot=None, unified=None, unified_runs=None, private_fallback=None):
    """Return (action, reason), never edit data, never declare Incheon healthy."""
    if selected in {"skip-active-run", "skip-status-running"}:
        return selected, "another official writer is active"
    latest_verified = verified_snapshot(report, snapshot)
    snapshot_age = now - latest_verified if latest_verified else None
    # Public display freshness and preemptive refresh timing are independent.
    # Keep draining missing Unified publications until the original 6-hour
    # deadline, but start the full regional re-scan at four hours.
    public_fresh = bool(snapshot_age is not None and timedelta(0) <= snapshot_age < timedelta(hours=6))
    refresh_not_due = bool(snapshot_age is not None and timedelta(0) <= snapshot_age < REGIONAL_REFRESH_AFTER)
    official_paused = selected in BLOCKED_ICE_ACTIONS
    # Regional collection may have succeeded while Unified still serves the
    # old 44-source version. Drain this publication backlog before private jobs.
    # Existing Unified circuit and recent-failure backoff remain binding.
    if public_fresh and not unified_has_snapshot(unified, snapshot):
        if selected in {"skip-unified-circuit-open", "skip-unified-backoff"}:
            return selected, "regional snapshot verified but Unified circuit/backoff is active"
        allowed, reason = unified_retry_gate(unified_runs, latest_verified, now)
        if not allowed:
            if official_paused:
                return "skip-incheon-hold", reason
            if selected == "unified":
                return "skip-unified-backoff", reason
            return selected, reason
        return "unified", "verified regional snapshot exists but is missing from Unified display"
    if refresh_not_due:
        if official_paused and private_fallback in ALLOWED_PRIVATE_FALLBACK:
            return private_fallback, "verified Seoul/Gyeonggi current, Incheon held; use circuit-checked isolated private slot"
        return ("skip-incheon-hold", "verified regional snapshot fresh; full ICE pipeline held") if official_paused else (selected, "verified regional snapshot fresh")
    active = [r for r in runs if r.get("event") == "workflow_dispatch" and
              r.get("head_branch") == "main" and r.get("status") in ACTIVE]
    if active:
        return ("skip-incheon-hold", "regional refresh already active") if official_paused else (selected, "regional refresh already active")
    finished = sorted(
        (r for r in runs if r.get("event") == "workflow_dispatch" and
         r.get("head_branch") == "main" and r.get("status") == "completed"),
        key=lambda r: str(r.get("updated_at") or r.get("created_at") or ""), reverse=True
    )
    if finished and finished[0].get("conclusion") in FAILED:
        ended = parse_time(finished[0].get("updated_at") or finished[0].get("created_at"))
        if ended and timedelta(0) <= now - ended < timedelta(hours=6):
            # The regional retry is still blocked. An independently guarded
            # private collector may use this idle slot only if the last
            # verified regional snapshot is also the one already published.
            # Its age is unchanged; never pretend the official refresh ran.
            if (
                official_paused
                and private_fallback in ALLOWED_PRIVATE_FALLBACK
                and private_fallback != "private-foundation"
                and snapshot_age is not None
                and snapshot_age >= timedelta(0)
                and unified_has_snapshot(unified, snapshot)
                and isinstance(unified_runs, list)
                and not any(r.get("status") in ACTIVE for r in unified_runs
                            if isinstance(r, dict)
                            and r.get("event") == "workflow_dispatch"
                            and r.get("head_branch") == "main")
            ):
                return private_fallback, "regional writer in 6-hour failure backoff; preserve verified published snapshot and use circuit-checked private slot"
            return ("skip-incheon-hold", "regional writer in 6-hour failure backoff") if official_paused else (selected, "regional writer in failure backoff")
    return REGIONAL_ACTION, "Seoul/Gyeonggi snapshot missing or older than the 4-hour preemptive refresh threshold; Incheon held"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--selected-action", required=True)
    p.add_argument("--supervisor-state", default="/tmp/production-supervisor.json")
    p.add_argument("--report", default="seoul_gyeonggi_refresh_report.json")
    p.add_argument("--snapshot", default="seoul_gyeonggi_jobs.json")
    p.add_argument("--unified", default="unified_jobs.json")
    p.add_argument("--runs", required=True)
    p.add_argument("--unified-runs", required=True)
    p.add_argument("--github-output", required=True)
    a = p.parse_args()
    try:
        report = json.loads(Path(a.report).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        report = {}
    try:
        snapshot = json.loads(Path(a.snapshot).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        snapshot = {}
    try:
        unified = json.loads(Path(a.unified).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        unified = {}
    runs = json.loads(Path(a.runs).read_text(encoding="utf-8"))
    if not isinstance(runs, dict) or not isinstance(runs.get("workflow_runs"), list):
        raise SystemExit("cannot verify regional workflow run state")
    unified_run_data = json.loads(Path(a.unified_runs).read_text(encoding="utf-8"))
    if not isinstance(unified_run_data, dict) or not isinstance(unified_run_data.get("workflow_runs"), list):
        raise SystemExit("cannot verify Unified production writer run state")
    now = datetime.now(timezone.utc)
    try:
        supervisor_state = json.loads(Path(a.supervisor_state).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        supervisor_state = None
    fallback = valid_private_fallback(supervisor_state, a.selected_action, now)
    action, reason = decide(
        a.selected_action, report, runs["workflow_runs"], now,
        snapshot=snapshot, unified=unified, unified_runs=unified_run_data["workflow_runs"],
        private_fallback=fallback,
    )
    with open(a.github_output, "a", encoding="utf-8") as handle:
        handle.write(f"action={action}\n")
    print(json.dumps({"selected": action, "prior": a.selected_action, "reason": reason}, ensure_ascii=False))


if __name__ == "__main__":
    main()
