#!/usr/bin/env python3
"""Measure official-posting observation and user-visible publication latency.

This audit intentionally separates what the repository can prove exactly from what it
cannot. Official boards often expose only a registration *date*, so the report never
pretends to know an exact official-posted timestamp. Instead it measures:
1. GitHub Actions queue/run latency for the production paths.
2. The interval between successful verified Fast publications (observation-cadence proxy).
3. source_id_ledger firstSeen -> Unified success -> Pages deployment latency.
4. A conservative four-hour visibility SLO proxy:
   p95 Fast-success interval + p95 detected-to-Pages lag.

The report is read-only and never mutates production data.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

KST = timezone(timedelta(hours=9))
FAST_NAME = "Update 수도권 education jobs"
UNIFIED_NAME = "Unified recruitment search"
PAGES_NAME = "pages build and deployment"
WORKFLOW_NAMES = {
    FAST_NAME,
    UNIFIED_NAME,
    "Reconcile official recruitment source IDs",
    "Daily deep recruitment audit",
    "Official completeness deep audit",
    "Recover missing 수도권 education jobs",
    "Production operations watchdog",
}


def parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    for candidate in (
        text.replace(" KST", "+09:00"),
        text.replace("Z", "+00:00"),
    ):
        try:
            dt = datetime.fromisoformat(candidate)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=KST)
            return dt.astimezone(timezone.utc)
        except ValueError:
            pass
    return None


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    vals = sorted(float(x) for x in values)
    rank = max(1, math.ceil(q * len(vals)))
    return vals[min(len(vals) - 1, rank - 1)]


def stats(values: list[float], digits: int = 2) -> dict[str, Any]:
    if not values:
        return {"count": 0, "p50": None, "p95": None, "max": None}
    return {
        "count": len(values),
        "p50": round(percentile(values, 0.50) or 0.0, digits),
        "p95": round(percentile(values, 0.95) or 0.0, digits),
        "max": round(max(values), digits),
    }


def fetch_action_runs(repo: str, token: str, cutoff: datetime, max_pages: int = 12) -> list[dict]:
    out: list[dict] = []
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "gg-edujob-visibility-latency-audit",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    for page in range(1, max_pages + 1):
        url = f"https://api.github.com/repos/{repo}/actions/runs?per_page=100&page={page}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
        batch = payload.get("workflow_runs") or []
        if not batch:
            break
        out.extend(batch)
        oldest = min(
            (parse_time(x.get("created_at")) for x in batch if parse_time(x.get("created_at"))),
            default=None,
        )
        if oldest and oldest < cutoff - timedelta(hours=24):
            break
    return out


def workflow_stats(runs: list[dict], cutoff: datetime) -> dict[str, dict]:
    grouped: dict[str, list[dict]] = {}
    for run in runs:
        created = parse_time(run.get("created_at"))
        if not created or created < cutoff:
            continue
        name = str(run.get("name") or "")
        if name not in WORKFLOW_NAMES:
            continue
        grouped.setdefault(name, []).append(run)

    result = {}
    for name, items in grouped.items():
        queues = []
        durations = []
        success = 0
        failures = 0
        for run in items:
            created = parse_time(run.get("created_at"))
            started = parse_time(run.get("run_started_at")) or created
            completed = parse_time(run.get("updated_at"))
            if created and started:
                queues.append(max(0.0, (started - created).total_seconds() / 60))
            if started and completed:
                durations.append(max(0.0, (completed - started).total_seconds() / 60))
            if run.get("conclusion") == "success":
                success += 1
            elif run.get("conclusion") in {"failure", "timed_out", "startup_failure"}:
                failures += 1
        result[name] = {
            "runs": len(items),
            "successes": success,
            "failures": failures,
            "queueMinutes": stats(queues),
            "durationMinutes": stats(durations),
        }
    return result


def completed_successes(runs: list[dict], name: str) -> list[tuple[datetime, dict]]:
    found = []
    for run in runs:
        if run.get("name") != name or run.get("conclusion") != "success":
            continue
        completed = parse_time(run.get("updated_at"))
        if completed:
            found.append((completed, run))
    return sorted(found, key=lambda x: x[0])


def completion_gaps_hours(successes: list[tuple[datetime, dict]], cutoff: datetime) -> list[float]:
    gaps = []
    for (prev_time, _), (cur_time, _) in zip(successes, successes[1:]):
        if cur_time < cutoff:
            continue
        gaps.append((cur_time - prev_time).total_seconds() / 3600)
    return gaps


def load_ledger(path: str | Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("entries"), dict):
        raise ValueError("source_id_ledger.json does not contain an entries object")
    return data


def first_seen_samples(ledger: dict, cutoff: datetime) -> tuple[list[dict], list[dict]]:
    rows = []
    for sid, entry in (ledger.get("entries") or {}).items():
        if not isinstance(entry, dict):
            continue
        seen = parse_time(entry.get("firstSeen"))
        if not seen or seen < cutoff:
            continue
        rows.append({
            "sourceIdentity": sid,
            "province": entry.get("province") or "",
            "source": entry.get("source") or "",
            "registered": entry.get("registered") or "",
            "firstSeen": seen,
        })
    rows.sort(key=lambda x: x["firstSeen"])

    counts = Counter(x["firstSeen"].isoformat() for x in rows)
    batches = [
        {"firstSeen": key, "newOfficialIds": count}
        for key, count in sorted(counts.items())
    ]
    return rows, batches


def next_success(
    successes: list[tuple[datetime, dict]],
    after: datetime,
    *,
    max_wait: timedelta | None = None,
) -> tuple[datetime, dict] | None:
    for completed, run in successes:
        if completed < after:
            continue
        if max_wait is not None and completed - after > max_wait:
            return None
        return completed, run
    return None


def visibility_samples(
    entries: list[dict],
    unified_successes: list[tuple[datetime, dict]],
    pages_successes: list[tuple[datetime, dict]],
) -> list[dict]:
    out = []
    for entry in entries:
        seen = entry["firstSeen"]
        unified = next_success(unified_successes, seen, max_wait=timedelta(hours=6))
        if not unified:
            continue
        unified_time, unified_run = unified
        pages = next_success(pages_successes, unified_time, max_wait=timedelta(minutes=20))
        if not pages:
            continue
        pages_time, pages_run = pages
        out.append({
            "sourceIdentity": entry["sourceIdentity"],
            "province": entry["province"],
            "source": entry["source"],
            "registered": entry["registered"],
            "firstSeen": seen.isoformat(),
            "unifiedCompletedAt": unified_time.isoformat(),
            "pagesCompletedAt": pages_time.isoformat(),
            "detectedToUnifiedMinutes": round((unified_time - seen).total_seconds() / 60, 2),
            "detectedToPagesMinutes": round((pages_time - seen).total_seconds() / 60, 2),
            "unifiedRunId": unified_run.get("id"),
            "pagesRunId": pages_run.get("id"),
        })
    return out


def build_report(
    *,
    ledger: dict,
    runs: list[dict],
    now: datetime,
    window_hours: int,
    slo_hours: float,
) -> dict:
    cutoff = now - timedelta(hours=window_hours)
    wf = workflow_stats(runs, cutoff)
    fast = completed_successes(runs, FAST_NAME)
    unified = completed_successes(runs, UNIFIED_NAME)
    pages = completed_successes(runs, PAGES_NAME)

    fast_gaps = completion_gaps_hours(fast, cutoff)
    entries, batches = first_seen_samples(ledger, cutoff)
    samples = visibility_samples(entries, unified, pages)
    detected_to_unified = [x["detectedToUnifiedMinutes"] for x in samples]
    detected_to_pages = [x["detectedToPagesMinutes"] for x in samples]

    gap_stats = stats(fast_gaps)
    detected_pages_stats = stats(detected_to_pages)
    p95_gap = gap_stats.get("p95")
    p95_detected_pages = detected_pages_stats.get("p95")

    proxy = None
    status = "insufficient-data"
    if p95_gap is not None and p95_detected_pages is not None and len(fast_gaps) >= 3:
        proxy = round(float(p95_gap) + float(p95_detected_pages) / 60, 2)
        status = "pass" if proxy < slo_hours else "fail"

    provinces = Counter(x["province"] or "unknown" for x in entries)
    return {
        "generatedAt": now.astimezone(KST).isoformat(timespec="seconds"),
        "windowHours": window_hours,
        "policy": "visibility-latency-audit-v1",
        "measurementLimits": {
            "officialRegistrationTimestamp": "Most official sources expose date-only registration values; exact official-posted-to-firstSeen latency is not asserted.",
            "firstSeen": "source_id_ledger firstSeen is the first independent stable-ID observation, not necessarily the exact instant the official site published.",
            "sloProxy": "p95 interval between successful Fast publications plus p95 firstSeen-to-Pages lag; conservative operational proxy, not a fabricated official timestamp.",
        },
        "workflowStats": wf,
        "observationCadence": {
            "successfulFastPublicationGapHours": gap_stats,
            "successfulFastRunsConsidered": len(fast),
        },
        "newOfficialIds": {
            "count": len(entries),
            "byProvince": dict(sorted(provinces.items())),
            "firstSeenBatches": batches[-30:],
        },
        "detectedToVisible": {
            "matchedSamples": len(samples),
            "detectedToUnifiedMinutes": stats(detected_to_unified),
            "detectedToPagesMinutes": detected_pages_stats,
            "sample": samples[-20:],
        },
        "fourHourVisibilitySloProxy": {
            "targetHours": slo_hours,
            "proxyP95Hours": proxy,
            "status": status,
            "reason": (
                "Fast publication cadence is too sparse for a four-hour visibility objective."
                if status == "fail"
                else "Operational timing evidence is within the four-hour proxy."
                if status == "pass"
                else "Need at least three successful Fast intervals and matched firstSeen-to-Pages samples."
            ),
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "teacherhub-kr/gg-edujob"))
    ap.add_argument("--token", default=os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or "")
    ap.add_argument("--ledger", default="source_id_ledger.json")
    ap.add_argument("--runs-json", default="")
    ap.add_argument("--output", default="visibility_latency_report.json")
    ap.add_argument("--window-hours", type=int, default=48)
    ap.add_argument("--slo-hours", type=float, default=4.0)
    ap.add_argument("--enforce", action="store_true")
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=args.window_hours)
    ledger = load_ledger(args.ledger)
    if args.runs_json:
        runs_payload = json.loads(Path(args.runs_json).read_text(encoding="utf-8"))
        runs = runs_payload.get("workflow_runs", runs_payload) if isinstance(runs_payload, dict) else runs_payload
    else:
        runs = fetch_action_runs(args.repo, args.token, cutoff)
    report = build_report(
        ledger=ledger,
        runs=list(runs or []),
        now=now,
        window_hours=args.window_hours,
        slo_hours=args.slo_hours,
    )
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "generatedAt": report["generatedAt"],
        "newOfficialIds": report["newOfficialIds"]["count"],
        "fastGapP95Hours": report["observationCadence"]["successfulFastPublicationGapHours"]["p95"],
        "detectedToPagesP95Minutes": report["detectedToVisible"]["detectedToPagesMinutes"]["p95"],
        "sloProxy": report["fourHourVisibilitySloProxy"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    slo = report["fourHourVisibilitySloProxy"]
    if slo["status"] == "fail":
        print(
            "::warning title=Official visibility SLO proxy exceeded::"
            f"proxyP95Hours={slo['proxyP95Hours']} targetHours={slo['targetHours']}"
        )
    if args.enforce and slo["status"] == "fail":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
