#!/usr/bin/env python3
"""Read-only audit for the maintenance freeze with one explicit P0 recovery exception.

Automatic state-changing workflows remain frozen except the dedicated Fast freshness watchdog,
which may run on ``schedule`` and dispatch the already-guarded Fast workflow only when the
repository's existing stale/active checks allow it.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"

FORBIDDEN_AUTOMATIC_EVENTS = {"schedule", "workflow_run", "repository_dispatch"}
ALLOWED_AUTOMATIC_EVENTS = {
    "fast-refresh-watchdog.yml": {"schedule"},
    # Read-only notification delivery. It cannot write repository state and
    # safely skips when the external alert backend secrets are not configured.
    "job-alerts.yml": {"schedule"},
}
WRITE_MARKERS = (
    "contents: write",
    "actions: write",
    "pull-requests: write",
    "git commit",
    "git push",
    "gh pr merge",
    "mergepullrequest",
    "enablepullrequestautomerge",
    "/dispatches",
    "gh workflow run",
    "/cancel",
)
DISPATCH_OR_MERGE_MARKERS = (
    "gh workflow run",
    "/dispatches",
    "gh pr merge",
    "mergepullrequest",
    "enablepullrequestautomerge",
)


def trigger_block(lines: list[str]) -> tuple[int, int, list[str]]:
    start = next((i for i, line in enumerate(lines) if line == "on:"), -1)
    if start < 0:
        raise ValueError("missing top-level on block")
    end = start + 1
    while end < len(lines) and (not lines[end] or lines[end][0].isspace()):
        end += 1
    return start, end, lines[start + 1 : end]


def events(block: list[str]) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    current = ""
    for line in block:
        match = re.match(r"^  ([A-Za-z_]+):", line)
        if match:
            current = match.group(1)
            found[current] = [line]
        elif current:
            found[current].append(line)
    return found


def push_reaches_main(block: list[str]) -> bool:
    text = "\n".join(block)
    branches = re.search(r"(?ms)^    branches:\s*(.*?)(?=^    [A-Za-z_]+:|^  [A-Za-z_]+:|\Z)", text)
    if not branches:
        return True
    value = branches.group(1)
    return bool(re.search(r"(^|[\s\[,])main([\s\],]|$)", value))


def step_blocks(lines: list[str]) -> list[list[str]]:
    starts = [i for i, line in enumerate(lines) if re.match(r"^      - (name|uses|run):", line)]
    return [lines[start : starts[n + 1] if n + 1 < len(starts) else len(lines)] for n, start in enumerate(starts)]


def excludes_pull_request(step: list[str]) -> bool:
    condition = " ".join(line.strip() for line in step if line.lstrip().startswith("if:"))
    guards = (
        "github.event_name != 'pull_request'",
        'github.event_name != "pull_request"',
        "github.event_name == 'workflow_dispatch'",
        'github.event_name == "workflow_dispatch"',
        "github.event_name == 'push'",
        'github.event_name == "push"',
        "github.event_name == 'schedule'",
        'github.event_name == "schedule"',
        "github.event_name == 'workflow_run'",
        'github.event_name == "workflow_run"',
    )
    return any(guard in condition for guard in guards)


def automatic_exception(path: Path, event: str) -> bool:
    return event in ALLOWED_AUTOMATIC_EVENTS.get(path.name, set())


def main() -> int:
    failures: list[str] = []
    totals: Counter[str] = Counter()
    workflow_files = sorted((*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml")))

    for path in workflow_files:
        lines = path.read_text(encoding="utf-8").splitlines()
        lowered = "\n".join(lines).lower()
        try:
            _, _, raw_block = trigger_block(lines)
        except ValueError as exc:
            failures.append(f"{path.name}: {exc}")
            continue
        configured = events(raw_block)
        totals.update(configured.keys())

        forbidden = sorted(
            event for event in FORBIDDEN_AUTOMATIC_EVENTS.intersection(configured)
            if not automatic_exception(path, event)
        )
        if forbidden:
            failures.append(f"{path.name}: forbidden automatic trigger(s): {', '.join(forbidden)}")

        state_changing = any(marker in lowered for marker in WRITE_MARKERS)
        if state_changing and "push" in configured and push_reaches_main(configured["push"]):
            failures.append(f"{path.name}: state-changing push can run on main")

        dispatch_or_merge = any(marker in lowered for marker in DISPATCH_OR_MERGE_MARKERS)
        automatic_events = {
            event for event in set(configured) - {"workflow_dispatch", "pull_request"}
            if not automatic_exception(path, event)
        }
        if dispatch_or_merge and automatic_events:
            failures.append(
                f"{path.name}: dispatch/merge logic exposed to automatic trigger(s): "
                + ", ".join(sorted(automatic_events))
            )

        if "pull_request" in configured:
            totals["read_only_pull_request_workflows"] += 1
            for step in step_blocks(lines):
                body = "\n".join(step).lower()
                if any(marker in body for marker in WRITE_MARKERS[3:]) and not excludes_pull_request(step):
                    name = next((line.strip() for line in step if line.lstrip().startswith("- name:")), "unnamed step")
                    failures.append(f"{path.name}: PR-reachable state-changing step: {name}")

    print(f"Audited {len(workflow_files)} workflow files")
    print("Triggers: " + ", ".join(f"{key}={totals[key]}" for key in sorted(totals) if key != "read_only_pull_request_workflows"))
    print(f"Read-only pull_request workflows: {totals['read_only_pull_request_workflows']}")
    print("Allowed automatic exceptions: fast-refresh-watchdog.yml schedule, job-alerts.yml schedule")
    if failures:
        print("Maintenance freeze audit FAILED", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print("Maintenance freeze audit PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
