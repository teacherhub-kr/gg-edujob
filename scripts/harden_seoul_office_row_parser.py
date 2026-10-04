#!/usr/bin/env python3
"""Validate the materialized Seoul support-office parser contract.

Historical versions of this helper rewrote ``scrape_jobs.py`` at CI/runtime.  The
parser is now reviewed source code, so this command is deliberately read-only: it
fails when the required contract drifts instead of mutating production code.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "scripts" / "scrape_jobs.py"

REQUIRED_MARKERS = (
    "def seoul_detail_anchor_for_seq(tr, seq):",
    "def seoul_row_values(table, tr):",
    "SEOUL_EMPTY_FIELD_VALUES",
    "def meaningful_seoul_value(value):",
    "def seoul_subject_from_values(vals):",
    "def seoul_title_from_values(vals, fallback=\"\"):",
    "parse_incomplete += 1",
    "seoulOfficeParseIncomplete",
)

FORBIDDEN_MARKERS = (
    "if len(title)<3 or EXCLUDE_WORDS.search(title): continue",
)


def main() -> None:
    text = TARGET.read_text(encoding="utf-8")
    missing = [marker for marker in REQUIRED_MARKERS if marker not in text]
    forbidden = [marker for marker in FORBIDDEN_MARKERS if marker in text]
    if missing or forbidden:
        details = []
        if missing:
            details.append("missing=" + ", ".join(missing))
        if forbidden:
            details.append("forbidden=" + ", ".join(forbidden))
        raise SystemExit("Seoul office parser contract drift: " + "; ".join(details))
    compile(text, str(TARGET), "exec")
    print("Seoul office row parser contract verified; no source mutation performed")


if __name__ == "__main__":
    main()
