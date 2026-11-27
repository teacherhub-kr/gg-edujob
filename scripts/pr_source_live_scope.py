#!/usr/bin/env python3
"""Decide if a PR must re-read a private recruitment board during CI.

Shared projection/registry changes remain covered by Unified validation and
historical source fixtures. Changes to a source's own crawler, fixture, exact
link logic or source artifacts still require its independent live proof.
Production workflow_dispatch always runs live (enforced by workflow YAML).
"""
from __future__ import annotations

import argparse
import subprocess

SOURCE_SPECIFIC_PATHS = {
    "seekle": frozenset({
        "scripts/crawl_seekle_instructor_jobs.py",
        "scripts/direct_post_links.py",
        "tests/test_seekle_historical_fixture.py",
        "tests/fixtures/seekle_21827.html",
        "seekle_jobs.json",
        "seekle_reconciliation_report.json",
    }),
    "boramyc": frozenset({
        "scripts/crawl_boramyc_instructor_jobs.py",
        "scripts/direct_post_links.py",
        "tests/test_boramyc_historical_fixture.py",
        "tests/fixtures/boramyc_25441.html",
        "boramyc_jobs.json",
        "boramyc_reconciliation_report.json",
    }),
}


def requires_live_probe(source: str, changed_paths) -> bool:
    if source not in SOURCE_SPECIFIC_PATHS:
        raise ValueError(f"unknown private source: {source}")
    return bool(SOURCE_SPECIFIC_PATHS[source].intersection(changed_paths))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=tuple(SOURCE_SPECIFIC_PATHS), required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", default="HEAD")
    args = parser.parse_args()
    result = subprocess.run(
        ["git", "diff", "--name-only", args.base, args.head, "--"],
        capture_output=True, text=True, check=True,
    )
    changes = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    needed = requires_live_probe(args.source, changes)
    # One line is deliberately suitable for GITHUB_OUTPUT.
    print(f"required={'true' if needed else 'false'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
