#!/usr/bin/env python3
"""Isolated Seoul/Gyeonggi official snapshot; never read or crawl Incheon.

The existing jobs.json / 44-source official reconciliation remain untouched.
Output is a separately verified 38-source regional snapshot for Unified.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from source_registry import official_source_breakdown

ROOT = Path(__file__).resolve().parents[1]
KST = timezone(timedelta(hours=9))
REGIONS = {"gyeonggi": "경기", "seoul": "서울"}
POLICY = "seoul-gyeonggi-isolated-verified-v1"


def read(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object at {path}")
    return data


def require(condition, message):
    if not condition:
        raise ValueError(message)


def merge_central_90d():
    import crawl_gyeonggi_central_recent as central
    from stable_source_identity import canonical_source_id

    data = read(ROOT / "jobs.json")
    require(set(data.get("sources") or {}) == set(REGIONS), "primary crawler must only cover Seoul/Gyeonggi")
    rows = central.scrape_gyeonggi_central_recent()
    health = getattr(central.scrape_gyeonggi_central_recent, "last_coverage", [])
    require(bool(rows) and bool(health), "empty Gyeonggi central 90-day crawl")
    require(all(h.get("coverageComplete") and not h.get("accessError") and not h.get("paginationRepeated")
                for h in health), "Gyeonggi central 90-day traversal incomplete")
    current = data.get("jobs") or []
    seen = {canonical_source_id(j) or str(j.get("id") or "") for j in current}
    added = 0
    for row in rows:
        key = canonical_source_id(row) or str(row.get("id") or "")
        require(bool(key) and row.get("province") == "경기", "invalid central identity/province")
        if key not in seen:
            current.append(row)
            seen.add(key)
            added += 1
    data["regionalCentral90d"] = {
        "coverageComplete": True,
        "sourceRows": len(rows),
        "pagesScanned": sum(int(h.get("pagesScanned") or 0) for h in health),
        "newlyAdded": added,
        "boardHealth": health,
    }
    data["jobs"] = sorted(current, key=lambda j: (str(j.get("registered") or ""), str(j.get("applyEnd") or "")), reverse=True)
    (ROOT / "jobs.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Regional Gyeonggi 90d crawl: {len(rows)} verified rows, {added} merged")


def validate_snapshot(candidate, registry, central, gyeonggi90, prior=None):
    breakdown = official_source_breakdown(ROOT / "sources.json")
    require(breakdown.get("gyeonggi") == 26 and breakdown.get("seoul") == 12,
            "Seoul/Gyeonggi registry must contain 26/12 official sources")
    require(set(candidate.get("sources") or {}) == set(REGIONS),
            "regional data must contain only Seoul/Gyeonggi source status")
    # The first, shallow collector can flag pages subsequently proven complete by
    # the independent full 90-day re-traversal below. Preserve its findings in
    # the report; the final 38-source proof, not an old shallow error, gates publish.
    rows = candidate.get("jobs")
    require(isinstance(rows, list) and len(rows) >= 100, "insufficient regional official jobs")
    require(all(isinstance(j, dict) and j.get("province") in REGIONS.values() for j in rows),
            "unexpected non-Seoul/Gyeonggi posting in regional snapshot")
    require(central.get("complete") is True and len(central.get("sources") or []) == 2,
            "independent Seoul/Gyeonggi central pagination not complete")
    require({item.get("province") for item in central["sources"]} == set(REGIONS.values()) and
            all(item.get("complete") and int(item.get("stableIdCount") or 0) >= 20
                for item in central["sources"]),
            "central source has incomplete or implausibly small population")
    require(gyeonggi90.get("complete") is True and gyeonggi90.get("lookbackDays") == 90 and
            int(gyeonggi90.get("stableIdCount") or 0) >= 20,
            "independent Gyeonggi central 90-day population missing")
    main90 = candidate.get("regionalCentral90d") or {}
    require(main90.get("coverageComplete") is True and
            int(main90.get("sourceRows") or 0) >= int(gyeonggi90.get("stableIdCount") or 0) * 0.95,
            "Gyeonggi 90-day scan disagrees materially with independent scan")
    comp = candidate.get("supportCompleteness") or {}
    require(int(comp.get("lookbackDays") or 0) == 90, "support offices must prove 90-day traversal")
    links = candidate.get("supportLinkResolution") or {}
    for key, province in REGIONS.items():
        group = candidate["sources"][key]
        office_expected = 25 if key == "gyeonggi" else 11
        require(group.get("central", {}).get("ok") is True and
                int(group["central"].get("count") or 0) >= 20,
                f"{province}: central source unhealthy")
        offices = group.get("supportOffices") or []
        want_names = {str(x.get("name") or "") for x in registry[key].get("supportOffices", [])}
        require(len(offices) == office_expected and
                {str(x.get("name") or "") for x in offices} == want_names,
                f"{province}: support-office registry mismatch")
        require(int(comp.get(key + "Complete") or 0) == office_expected and
                int(comp.get(key + "Total") or 0) == office_expected,
                f"{province}: support-office completeness count mismatch")
        for office in offices:
            boards = office.get("boardHealth") or []
            require(office.get("ok") is True and office.get("coverageComplete") is True
                    and bool(boards), f"{province}/{office.get('name')}: missing complete board evidence")
            for board in boards:
                require(board.get("coverageComplete") is True and
                        int(board.get("pagesScanned") or 0) > 0 and
                        int(board.get("pagesScanned") or 0) < 500 and
                        not board.get("accessError") and not board.get("paginationRepeated") and
                        (board.get("crossedLookback") or board.get("naturalEnd") or board.get("explicitEmpty")),
                        f"{province}/{office.get('name')}: unproven board traversal")
        total = int(links.get(key + "Total") or 0)
        exact = int(links.get(key + "Exact") or 0)
        require(total > 0 and exact == total,
                f"{province}: exact support detail links incomplete ({exact}/{total})")
    require(candidate.get("verification", {}).get("state") != "critical",
            "second-stage independent job/link verification is critical")
    if prior:
        historical = [j for j in prior.get("jobs", []) if isinstance(j, dict) and j.get("province") in REGIONS.values()]
        if len(historical) >= 500:
            require(len(rows) >= max(100, int(len(historical) * 0.30)),
                    "regional candidate dropped more than 70% of previous population")
    return {"gyeonggi": sum(j.get("province") == "경기" for j in rows),
            "seoul": sum(j.get("province") == "서울" for j in rows)}


def finalize():
    candidate = read(ROOT / "jobs.json")
    registry = read(ROOT / "sources.json")
    central = read(ROOT / "central_pagination_report.json")
    gyeonggi90 = read(ROOT / "gyeonggi_central_90d_report.json")
    previous_path = Path("/tmp/sg-official-previous.json")
    previous = read(previous_path) if previous_path.is_file() else None
    counts = validate_snapshot(candidate, registry, central, gyeonggi90, previous)
    generated = datetime.now(KST).isoformat(timespec="seconds")
    regional = {
        "policy": POLICY, "generatedAt": generated, "state": "verified",
        "refreshedRegions": ["경기", "서울"],
        "refreshedOfficialSourceCount": 38,
        "heldRegions": {"인천": {"state": "stale", "reason": "official collection isolated; not verified"}},
        "officialJobs": counts,
    }
    snapshot = {
        "updatedAt": generated,
        "officialSourceCount": 38,
        "sources": {key: candidate["sources"][key] for key in REGIONS},
        "regionalPublication": regional,
        "jobs": candidate["jobs"],
    }
    (ROOT / "seoul_gyeonggi_jobs.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    (ROOT / "seoul_gyeonggi_refresh_report.json").write_text(
        json.dumps({"generatedAt": generated, "state": "verified",
                    "policy": POLICY, "counts": counts,
                    "supportCompleteness": {k: candidate["supportCompleteness"][k]
                        for k in ("lookbackDays", "gyeonggiTotal", "gyeonggiComplete",
                                  "seoulTotal", "seoulComplete")},
                    "incheon": "untouched; not scanned",
                    "primaryCollectorWarnings": candidate.get("errors") or []},
                   ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(regional, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--merge-central", action="store_true")
    group.add_argument("--finalize", action="store_true")
    args = ap.parse_args()
    if args.merge_central:
        merge_central_90d()
    else:
        finalize()


if __name__ == "__main__":
    main()
