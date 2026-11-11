#!/usr/bin/env python3
"""Fail-closed, ID-level explanation for a large Lessoninfo active-population drop.

A stale previous snapshot can legitimately lose no-deadline records after 30 days.
An unexplained missing ID, route mismatch, parser regression or incomplete crawl
must still block publication. This never changes the collector's active policy.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

EXPLAINED_INACTIVE_REASONS = {"stale-without-deadline", "closed-marker"}
NO_DEADLINE_FRESH_DAYS = 30


def _rows(dataset: Any) -> list[dict]:
    if isinstance(dataset, list):
        return dataset
    if isinstance(dataset, dict) and isinstance(dataset.get("jobs"), list):
        return dataset["jobs"]
    raise ValueError("Lessoninfo drop guard: missing jobs array")


def _drop_scopes(previous: dict, current: dict) -> list[tuple[str, int, int]]:
    result: list[tuple[str, int, int]] = []
    prev_total = int(previous.get("activeIdCount") or previous.get("publishedIdCount") or 0)
    now_total = int(current.get("activeIdCount") or 0)
    if prev_total >= 50 and now_total * 100 < prev_total * 60:
        result.append(("all", prev_total, now_total))
    for key, raw in (previous.get("perSurfaceActive") or {}).items():
        old = int(raw or 0)
        new = int((current.get("perSurfaceActive") or {}).get(key) or 0)
        if old >= 20 and new * 100 < old * 60:
            result.append((key, old, new))
    return result


def validate_population_drop(
    previous_report: dict,
    current_report: dict,
    previous_dataset: Any,
    current_candidates_dataset: Any,
) -> list[str]:
    """Return audit lines for explained drops; raise ValueError for any unsafe drop."""
    if previous_report.get("healthy") is not True:
        return []
    drops = _drop_scopes(previous_report, current_report)
    if not drops:
        return []

    if (
        current_report.get("healthy") is not True
        or current_report.get("traversalComplete") is not True
        or current_report.get("detailErrorCount") != 0
        or current_report.get("missingAfterCount") != 0
    ):
        raise ValueError("Lessoninfo drop guard: incomplete current collection")

    try:
        current_day = datetime.fromisoformat(str(current_report["generatedAt"])).date()
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Lessoninfo drop guard: missing trustworthy collection date") from exc

    old_rows = _rows(previous_dataset)
    new_rows = _rows(current_candidates_dataset)
    if not old_rows or not new_rows:
        raise ValueError("Lessoninfo drop guard: previous or current ID evidence absent")

    previous_ids = [str(r.get("sourceIdentity") or "") for r in old_rows]
    current_ids = [str(r.get("sourceIdentity") or "") for r in new_rows]
    if (
        not all(previous_ids)
        or len(previous_ids) != len(set(previous_ids))
        or not all(current_ids)
        or len(current_ids) != len(set(current_ids))
    ):
        raise ValueError("Lessoninfo drop guard: missing or duplicate stable IDs")

    current_map = {str(row["sourceIdentity"]): row for row in new_rows}
    current_active = [r for r in new_rows if r.get("isCurrent") is True]
    if len(current_active) != int(current_report.get("activeIdCount") or 0):
        raise ValueError("Lessoninfo drop guard: active set/report count mismatch")
    if len(new_rows) != int(current_report.get("candidateIdCount") or 0):
        raise ValueError("Lessoninfo drop guard: candidate count/report mismatch")

    evidence: list[str] = []
    for scope, old_count, new_count in drops:
        def in_scope(row: dict) -> bool:
            return scope == "all" or row.get("sourceSurface") == scope

        old_set = {str(r["sourceIdentity"]) for r in old_rows if in_scope(r)}
        active_set = {str(r["sourceIdentity"]) for r in current_active if in_scope(r)}
        # Previous public view may exclude one non-metro record found in the
        # private reconciliation report, but a larger discrepancy is unsafe.
        if len(old_set) < old_count - 1 or len(active_set) != new_count:
            raise ValueError(
                f"Lessoninfo drop guard: {scope} snapshot count inconsistent "
                f"({len(old_set)}/{old_count}, {len(active_set)}/{new_count})"
            )
        absent = old_set - active_set
        if not absent:
            raise ValueError(f"Lessoninfo drop guard: {scope} drop lacks ID explanation")
        unresolved = []
        reason_counts: dict[str, int] = {}
        for stable_id in sorted(absent):
            row = current_map.get(stable_id)
            reason = str((row or {}).get("classificationReason") or "")
            if not row or not in_scope(row) or row.get("isCurrent") is True or reason not in EXPLAINED_INACTIVE_REASONS:
                unresolved.append(f"{stable_id}:{reason or 'missing'}")
                continue
            if reason == "stale-without-deadline":
                try:
                    registered = date.fromisoformat(str(row.get("registered") or "")[:10])
                except ValueError:
                    unresolved.append(f"{stable_id}:missing-registered-date")
                    continue
                if (current_day - registered).days <= NO_DEADLINE_FRESH_DAYS:
                    unresolved.append(f"{stable_id}:not-older-than-{NO_DEADLINE_FRESH_DAYS}d")
                    continue
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        if unresolved:
            raise ValueError(
                f"Lessoninfo unexplained {scope} drop: {new_count}/{old_count}; "
                f"unsafe IDs={unresolved[:12]}; last-known-good preserved"
            )
        evidence.append(
            f"Lessoninfo {scope} ID-explained drop: {new_count}/{old_count}; "
            f"retired={len(absent)} reasons={reason_counts}"
        )
    return evidence
