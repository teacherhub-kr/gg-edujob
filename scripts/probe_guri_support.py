#!/usr/bin/env python3
"""PR-only, read-only live official Guri-Namyangju recruitment completeness proof.

Only the five known recruitment boards are requested. No jobs.json writes, no
new GitHub commits and no production publication. Failure preserves existing
data and identifies the exact URL/page-proof defect for the next repair.
"""
from __future__ import annotations

import json
import sys

import complete_support_coverage as crawler


def main():
    src = next(
        x for x in crawler.SOURCES["gyeonggi"]["supportOffices"]
        if x["name"] == "구리남양주교육지원청"
    )
    boards = crawler.official_support_board_urls(
        src, crawler.CACHE.get(src["name"], [])
    )
    if len(boards) != 5:
        raise SystemExit("Guri five-board official recruitment contract missing")

    failures = []
    for board in boards:
        rows, meta = crawler.gyeonggi_board(board, src)
        meta = {**meta, "parsedRecruitmentRows": len(rows)}
        print("GURI_OFFICIAL_BOARD_PROOF", json.dumps(meta, ensure_ascii=False), flush=True)
        if not meta["coverageComplete"] or meta["accessError"] or meta["paginationRepeated"]:
            failures.append(board)
    if failures:
        print("GURI_LIVE_PROOF_FAILED", json.dumps(failures, ensure_ascii=False), flush=True)
        return 1
    print("GURI_LIVE_PROOF_PASSED 5/5 canonical official recruitment boards", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
