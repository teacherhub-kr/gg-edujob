#!/usr/bin/env python3
"""Select one overdue, circuit-checked private writer in an independent schedule.

This read-only decision reuses production_supervisor policy. It never touches the
official collectors, bypasses a backoff, or edits production data.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import os

import private_refresh_policy as policy
import production_supervisor as supervisor


def choose(now, repo):
    policy.apply_private_refresh_policy()
    policy.register_lessoninfo_link_verification()

    keys = (*supervisor.PRIVATE_REFRESH_TARGETS.keys(), supervisor.ARTMORE_PROMOTE_KEY)
    all_runs = {key: supervisor.gh_runs(repo, supervisor.TARGETS[key]) for key in keys}
    active_snapshot = supervisor.gh_active_target_keys(repo)
    active_private = [
        key for key in keys
        if key in active_snapshot
        or any(r.get("status") in supervisor.ACTIVE_STATES for r in all_runs[key])
    ]
    last_refresh = {
        key: supervisor.git_commit_time(str(spec["report"]))
        for key, spec in supervisor.PRIVATE_REFRESH_TARGETS.items()
    }
    freshness = {}
    for key, spec in supervisor.PRIVATE_REFRESH_TARGETS.items():
        at = last_refresh[key]
        max_hours = int(spec["maxAgeHours"])
        freshness[key] = {
            "ageHours": round((now - at).total_seconds() / 3600, 2) if at else None,
            "maxAgeHours": max_hours,
            "overdue": supervisor.private_refresh_due(at, now, max_hours),
        }

    action, reason = supervisor.choose_private_refresh_action(
        now=now,
        all_runs=all_runs,
        private_refresh_times=last_refresh,
        private_freshness=freshness,
        active_private=active_private,
    )
    if action not in keys or not action.startswith("private-"):
        return None, None, reason or "all private sources current or safely backed off"
    return action, supervisor.TARGETS[action], reason


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    p.add_argument("--github-output", required=True)
    args = p.parse_args()
    if not args.repo:
        raise SystemExit("GITHUB_REPOSITORY is required")
    action, workflow, reason = choose(datetime.now(supervisor.KST), args.repo)
    with open(args.github_output, "a", encoding="utf-8") as output:
        output.write("action=" + (action or "") + "\n")
        output.write("workflow=" + (workflow or "") + "\n")
    print(f"private-lane selection: action={action or 'skip'} reason={reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
