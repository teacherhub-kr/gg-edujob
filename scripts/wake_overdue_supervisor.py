#!/usr/bin/env python3
"""Fail-closed overdue-watchdog wake decision for an existing approved scheduler.

This script is read-only; the scheduled workflow may dispatch the existing
watchdog only after a second independent eligibility check. It never runs
collectors, changes source data, or edits production state itself.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ACTIVE = {"queued", "in_progress", "waiting", "requested", "pending"}
ELIGIBLE_EVENTS = {"schedule", "workflow_dispatch"}
STALE_AFTER = timedelta(minutes=90)
CLOCK_SKEW = timedelta(minutes=5)


def parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.astimezone(timezone.utc) if dt.tzinfo else None


def should_wake(data: object, now: datetime) -> tuple[bool, str]:
    """A stale watchdog is a wake candidate; missing/ambiguous evidence is not."""
    if now.tzinfo is None:
        return False, "clock is timezone-naive"
    if not isinstance(data, dict) or not isinstance(data.get("workflow_runs"), list):
        return False, "workflow-run history unavailable"
    relevant = [
        run for run in data["workflow_runs"]
        if isinstance(run, dict)
        and run.get("event") in ELIGIBLE_EVENTS
        and run.get("head_branch") == "main"
    ]
    if not relevant:
        return False, "no previous main watchdog run to anchor freshness"
    if any(run.get("status") in ACTIVE for run in relevant):
        return False, "watchdog already active or queued"
    observed = []
    for run in relevant:
        when = parse_time(run.get("created_at"))
        if when is None:
            return False, "watchdog run lacks a valid created_at"
        observed.append(when)
    latest = max(observed)
    current = now.astimezone(timezone.utc)
    if latest > current + CLOCK_SKEW:
        return False, "GitHub and runner clock disagree"
    age = current - latest
    if age <= STALE_AFTER:
        return False, f"recent watchdog run {int(age.total_seconds() // 60)}m ago"
    return True, f"no new watchdog run for {int(age.total_seconds() // 60)}m"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", required=True)
    parser.add_argument("--github-output")
    args = parser.parse_args()
    try:
        history = json.loads(Path(args.runs).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"watchdog wake skipped: unable to read run history: {exc}")
        # API/read failures are infrastructure errors; exit nonzero, never dispatch.
        return 2
    wake, reason = should_wake(history, datetime.now(timezone.utc))
    print(json.dumps({"wake": wake, "reason": reason}, ensure_ascii=False))
    if args.github_output:
        with Path(args.github_output).open("a", encoding="utf-8") as handle:
            handle.write(f"wake={'true' if wake else 'false'}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
