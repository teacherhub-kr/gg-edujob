#!/usr/bin/env python3
"""Wake the single production watchdog when GitHub schedule activity is stale.

The external heartbeat never decides which production writer to run.
It may only dispatch fast-refresh-watchdog.yml on main.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

REPO = "teacherhub-kr/gg-edujob"
WORKFLOW = "fast-refresh-watchdog.yml"
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
        status, raw = request(
            "GET",
            f"/actions/workflows/{WORKFLOW}/runs?per_page=20",
            token,
        )
        if status != 200:
            emit("fatal", reason="unexpected runs response", httpStatus=status)
            return 2

        runs = (json.loads(raw.decode("utf-8")) or {}).get("workflow_runs") or []
        now = datetime.now(timezone.utc)

        active = [r for r in runs if str(r.get("status") or "") in ACTIVE]
        if active:
            newest = max(
                (
                    parse_time(r.get("run_started_at"))
                    or parse_time(r.get("created_at"))
                    for r in active
                ),
                default=None,
            )
            emit(
                "skip-active",
                activeCount=len(active),
                newestActiveAt=newest.isoformat() if newest else None,
            )
            return 0

        latest_activity = max(
            (
                parse_time(r.get("run_started_at"))
                or parse_time(r.get("created_at"))
                for r in runs
            ),
            default=None,
        )
        if latest_activity and now - latest_activity <= RECENT_WINDOW:
            emit(
                "skip-recent",
                latestActivityAt=latest_activity.isoformat(),
                ageMinutes=round((now - latest_activity).total_seconds() / 60, 2),
                recentWindowMinutes=int(RECENT_WINDOW.total_seconds() / 60),
            )
            return 0

        status, _ = request(
            "POST",
            f"/actions/workflows/{WORKFLOW}/dispatches",
            token,
            {"ref": REF},
        )
        if status != 204:
            emit("fatal", reason="unexpected dispatch response", httpStatus=status)
            return 2

        emit(
            "dispatched",
            repo=REPO,
            workflow=WORKFLOW,
            ref=REF,
            previousActivityAt=latest_activity.isoformat() if latest_activity else None,
        )
        return 0
    except urllib.error.HTTPError as exc:
        emit("fatal", reason="github http error", httpStatus=exc.code)
        return 2
    except Exception as exc:
        emit("transient-failure", reason=f"{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
