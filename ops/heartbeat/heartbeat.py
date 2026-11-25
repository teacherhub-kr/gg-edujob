#!/usr/bin/env python3
"""Wake the verified production watchdog when GitHub schedule activity is stale.

The external heartbeat never decides which production writer to run.
It may only dispatch production-operations-watchdog.yml on main.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

REPO = "teacherhub-kr/gg-edujob"
WORKFLOW = "production-operations-watchdog.yml"
REF = "main"
API = f"https://api.github.com/repos/{REPO}"
RECENT_WINDOW = timedelta(minutes=20)
ACTIVE = {"queued", "in_progress", "waiting", "requested", "pending"}
RETRYABLE = {429, 500, 502, 503, 504}


def emit(status: str, **fields: object) -> None:
    print(json.dumps({"status": status, **fields}, ensure_ascii=False, sort_keys=True), flush=True)


def parse_time(value: object) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def request(method: str, path: str, token: str, body: dict | None = None) -> tuple[int, bytes]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "gg-edujob-railway-heartbeat/1",
    }
    delays = (0, 5, 15)
    last_error: Exception | None = None
    for attempt, delay in enumerate(delays, start=1):
        if delay:
            time.sleep(delay)
        req = urllib.request.Request(f"{API}{path}", data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in RETRYABLE or attempt == len(delays):
                raise
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            if attempt == len(delays):
                raise
    raise RuntimeError(f"request failed: {last_error}")


def inspect_watchdog(token: str) -> tuple[str, datetime | None, int]:
    """Fail closed on unknown history; only count production watchdog main runs."""
    status, raw = request(
        "GET", f"/actions/workflows/{WORKFLOW}/runs?per_page=40", token
    )
    if status != 200:
        raise ValueError(f"unexpected watchdog runs HTTP status: {status}")
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("workflow_runs"), list):
        raise ValueError("watchdog run list not available")
    runs = [
        run for run in payload["workflow_runs"]
        if isinstance(run, dict)
        and run.get("head_branch") == REF
        and run.get("event") in {"schedule", "workflow_dispatch"}
    ]
    if not runs:
        raise ValueError("no production watchdog history; refuse unbounded dispatch")
    times = [parse_time(run.get("run_started_at")) or parse_time(run.get("created_at")) for run in runs]
    if any(when is None for when in times):
        raise ValueError("watchdog history has invalid timestamps")
    if any(str(run.get("status") or "") in ACTIVE for run in runs):
        return "skip-active", max(times), sum(str(run.get("status") or "") in ACTIVE for run in runs)
    latest = max(times)
    if latest > datetime.now(timezone.utc) + timedelta(minutes=5):
        raise ValueError("watchdog history contains a future timestamp")
    if datetime.now(timezone.utc) - latest <= RECENT_WINDOW:
        return "skip-recent", latest, 0
    return "stale", latest, 0


def main() -> int:
    enabled = os.environ.get("HEARTBEAT_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}
    if not enabled:
        emit("disabled", reason="HEARTBEAT_ENABLED is not true")
        return 0
    token = os.environ.get("GH_DISPATCH_TOKEN", "").strip()
    if not token:
        emit("fatal", reason="GH_DISPATCH_TOKEN is missing")
        return 2
    try:
        # Read twice: an independent GitHub schedule or other heartbeat can
        # start between probes. Never guess the state from a failed/empty read.
        for attempt in (1, 2):
            action, latest, active_count = inspect_watchdog(token)
            if action == "skip-active":
                emit(action, activeCount=active_count, latestActivityAt=latest.isoformat(), check=attempt)
                return 0
            if action == "skip-recent":
                emit(action, latestActivityAt=latest.isoformat(), check=attempt)
                return 0
        status, _ = request(
            "POST", f"/actions/workflows/{WORKFLOW}/dispatches", token, {"ref": REF}
        )
        if status != 204:
            emit("fatal", reason="unexpected dispatch response", httpStatus=status)
            return 2
        emit("dispatched", repo=REPO, workflow=WORKFLOW, ref=REF,
             previousActivityAt=latest.isoformat() if latest else None)
        return 0
    except urllib.error.HTTPError as exc:
        emit("fatal", reason="github http error", httpStatus=exc.code)
        return 2
    except (ValueError, json.JSONDecodeError) as exc:
        emit("fatal", reason=f"untrusted watchdog history: {exc}")
        return 2
    except Exception as exc:
        emit("transient-failure", reason=f"{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
