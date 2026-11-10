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


def decide(selected, report, runs, now):
    """Return (action, reason), never edit data, never declare Incheon healthy."""
    if selected in {"skip-active-run", "skip-status-running"}:
        return selected, "another official writer is active"
    if not isinstance(report, dict):
        report = {}
    latest_verified = parse_time(report.get("generatedAt")) if report.get("state") == "verified" else None
    fresh = bool(latest_verified and timedelta(0) <= now - latest_verified < timedelta(hours=6))
    official_paused = selected in BLOCKED_ICE_ACTIONS
    if fresh:
        return ("skip-incheon-hold", "regional snapshot fresh; full ICE pipeline held") if official_paused else (selected, "regional snapshot fresh")
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
            return ("skip-incheon-hold", "regional writer in 6-hour failure backoff") if official_paused else (selected, "regional writer in failure backoff")
    return REGIONAL_ACTION, "Seoul/Gyeonggi snapshot missing or older than 6 hours; Incheon held"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--selected-action", required=True)
    p.add_argument("--report", default="seoul_gyeonggi_refresh_report.json")
    p.add_argument("--runs", required=True)
    p.add_argument("--github-output", required=True)
    a = p.parse_args()
    try:
        report = json.loads(Path(a.report).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        report = {}
    runs = json.loads(Path(a.runs).read_text(encoding="utf-8"))
    if not isinstance(runs, dict) or not isinstance(runs.get("workflow_runs"), list):
        raise SystemExit("cannot verify regional workflow run state")
    action, reason = decide(a.selected_action, report, runs["workflow_runs"], datetime.now(timezone.utc))
    with open(a.github_output, "a", encoding="utf-8") as handle:
        handle.write(f"action={action}\n")
    print(json.dumps({"selected": action, "prior": a.selected_action, "reason": reason}, ensure_ascii=False))


if __name__ == "__main__":
    main()
