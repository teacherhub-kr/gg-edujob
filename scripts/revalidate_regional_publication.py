#!/usr/bin/env python3
"""Recheck a completed regional snapshot after unrelated writers advance main.

The transaction allows replay only when intervening paths are explicitly
classified as independent of the Seoul/Gyeonggi official collector.  This
check does not replace the original live 90-day traversal or source-ID audit.
"""
from __future__ import annotations

import json
from pathlib import Path

from build_unified_search_multi import verified_regional_snapshot
from source_registry import official_source_breakdown


def main() -> None:
    snapshot = verified_regional_snapshot()  # Fail closed on report/data mismatch.
    if snapshot is None:
        raise ValueError("Verified regional official snapshot is missing")
    breakdown = official_source_breakdown(Path("sources.json"))
    if breakdown.get("gyeonggi") != 26 or breakdown.get("seoul") != 12:
        raise ValueError("Seoul/Gyeonggi source registry changed during replay")
    report = json.loads(Path("seoul_gyeonggi_refresh_report.json").read_text(encoding="utf-8"))
    support = report.get("supportCompleteness") or {}
    if (support.get("lookbackDays") != 90
            or support.get("gyeonggiComplete") != 25
            or support.get("gyeonggiTotal") != 25
            or support.get("seoulComplete") != 11
            or support.get("seoulTotal") != 11):
        raise ValueError("Regional support-office 90-day proof is incomplete")
    central = report.get("seoulCentralIdReconciliation") or {}
    if central.get("verified") is not True or central.get("missingAfter") != 0:
        raise ValueError("Seoul central source-native ID reconciliation incomplete")
    if not snapshot.get("jobs") or not snapshot.get("regionalPublication"):
        raise ValueError("Verified regional payload is empty")
    print("VERIFIED_REGIONAL_REPLAY_UNCHANGED_OFFICIAL_INPUTS")


if __name__ == "__main__":
    main()
