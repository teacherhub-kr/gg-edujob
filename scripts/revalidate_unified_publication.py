#!/usr/bin/env python3
"""Rebuild a Unified publication on a newer main before any replayed push.

Only used by publication_transaction.py after every intervening main path has
matched an explicitly allowed canonical-data pattern.  This is deliberately
stricter than reusing a previously validated Unified snapshot: new source
commits must be incorporated, and every publication guard must pass again.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path


def run(*command: str) -> None:
    subprocess.run(list(command), check=True)


def verify_publication_contract() -> None:
    from direct_post_links import is_direct_post
    from private_source_registry import private_source_keys
    from source_registry import official_source_count

    payload = json.loads(Path("unified_jobs.json").read_text(encoding="utf-8"))
    rows = payload.get("jobs")
    if payload.get("dataset") != "unified-search-v3-multi-private" or not isinstance(rows, list):
        raise ValueError("Invalid Unified dataset or jobs population")
    private = payload.get("privateSources") or {}
    expected = set(private_source_keys())
    if set(private) != expected:
        raise ValueError("Private source registry differs from published dataset")
    official_count = official_source_count()
    if int(payload.get("officialSourceCount") or 0) != official_count:
        raise ValueError("Official source registry differs from published dataset")
    enabled = {key for key, meta in private.items() if meta.get("publicationEnabled") is True}
    if int(payload.get("totalSourceCount") or 0) != official_count + len(enabled):
        raise ValueError("Unified total source count is inconsistent")
    if not all(private[key].get("ok") for key in enabled):
        raise ValueError("Unhealthy source enabled for publication")
    if not any(row.get("feedKind") == "official" for row in rows):
        raise ValueError("No official postings found")
    if not any(row.get("feedKind") == "private" for row in rows):
        raise ValueError("No private postings found")
    disabled_names = {private[key].get("name") for key in expected - enabled}
    if any(row.get("feedKind") == "private" and row.get("source") in disabled_names for row in rows):
        raise ValueError("Publication-disabled private posting leaked")
    for key in enabled:
        if private[key].get("count") and not any(row.get("source") == private[key].get("name") for row in rows):
            raise ValueError(f"Enabled private source {key} disappeared from projected jobs")

    allowed = {"서울", "경기"}
    lesson_allowed = {"서울", "경기", "인천"}
    for row in rows:
        if row.get("feedKind") == "private":
            regions = {str(x) for x in (row.get("provinces") or []) if str(x)}
            if not regions and row.get("province"):
                regions = {str(row["province"])}
            lesson = row.get("source") == "레슨인포" and row.get("fullCandidate") is True
            if not ((not regions or regions <= lesson_allowed) if lesson else (bool(regions) and regions <= allowed)):
                raise ValueError("Non-metro private posting in Unified")
        if row.get("detailLinkVerified") is not False and not is_direct_post(row)[0]:
            raise ValueError("Non-direct clickable posting link")
        if row.get("sourceRole") == "primary-official" and row.get("sourceSurface") == "cultural-foundation":
            if not row.get("foundationRegistryId") or row.get("trustLevel") != "공식" or not is_direct_post(row)[0]:
                raise ValueError("Unverified primary cultural-foundation posting")
    report = json.loads(Path("unified_validation_report.json").read_text(encoding="utf-8"))
    if report.get("healthy") is not True or report.get("errors") or report.get("missingPrivateIds"):
        raise ValueError("Unified validation report has errors or missing private IDs")
    if len(rows) != report.get("total"):
        raise ValueError("Unified validation population differs from rebuilt dataset")
    app_js = Path("app.js").read_text(encoding="utf-8")
    index_html = Path("index.html").read_text(encoding="utf-8")
    for invariant in ("fetch('unified_jobs.json',{cache:'no-cache'})", "const provinceOptions=()=>['경기','서울','인천']"):
        if invariant not in app_js:
            raise ValueError("Unified frontend integration invariant missing")
    for invariant in ('<button type="button" data-surface="민간공고">민간공고</button>', "app.js?v="):
        if invariant not in index_html:
            raise ValueError("Unified frontend integration invariant missing")


def main() -> None:
    # Rebuild from the latest canonical inputs, not the stale cherry-picked JSON.
    run("python", "scripts/build_unified_search_multi.py")
    run("python", "scripts/audit_direct_post_links.py", "--input", "unified_jobs.next.json",
        "--repair-in-place", "--strict-clickable")
    run("python", "scripts/validate_unified_search_multi.py")
    run("python", "scripts/crosscheck_private_official.py")
    Path("unified_jobs.next.json").replace("unified_jobs.json")
    run("python", "scripts/validate_required_metro_publication.py")
    verify_publication_contract()
    # Fail closed if this additional section cannot be reconciled on replay.
    # Unlike the original run, never carry forward an unverified section.
    run("python", "scripts/reconcile_cultural_foundation_coverage.py")
    print("VERIFIED_UNIFIED_REPLAY_ON_LATEST_MAIN")


if __name__ == "__main__":
    main()
