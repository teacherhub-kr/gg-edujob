#!/usr/bin/env python3
"""Fail closed unless unified publication represents all mandatory official metro regions."""
from __future__ import annotations

import json
from pathlib import Path

from source_registry import official_source_count

REQUIRED_REGISTRY_GROUPS = {"gyeonggi", "seoul", "incheon"}
REQUIRED_PROVINCES = {"경기", "서울", "인천"}


def load_json(path: str) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"{path} must contain an object")
    return data


def provinces(row: dict) -> set[str]:
    explicit = {str(x) for x in (row.get("provinces") or []) if str(x)}
    if explicit:
        return explicit
    scalar = str(row.get("province") or "")
    return {scalar} if scalar else set()


def main() -> None:
    registry = load_json("sources.json")
    missing_registry = REQUIRED_REGISTRY_GROUPS - set(registry)
    if missing_registry:
        raise SystemExit(
            f"mandatory official registry groups missing: {sorted(missing_registry)}"
        )

    unified = load_json("unified_jobs.json")
    expected_sources = official_source_count()
    embedded_sources = int(unified.get("officialSourceCount") or 0)
    if embedded_sources != expected_sources:
        raise SystemExit(
            f"unified officialSourceCount={embedded_sources} expected={expected_sources}"
        )

    source_meta = unified.get("sources") or {}
    if not isinstance(source_meta, dict):
        raise SystemExit("unified source-status metadata must be an object")
    missing_source_meta = REQUIRED_REGISTRY_GROUPS - set(source_meta)
    if missing_source_meta:
        raise SystemExit(
            "unified source-status metadata missing mandatory groups: "
            f"{sorted(missing_source_meta)}"
        )

    official_rows = [
        row
        for row in (unified.get("jobs") or [])
        if isinstance(row, dict) and row.get("feedKind") == "official"
    ]
    published: set[str] = set()
    for row in official_rows:
        published.update(provinces(row))
    # Normal 44-source publication still requires all three provinces.
    # Only a separately verified regional snapshot may hold Incheon, and it
    # MUST NOT display an old Incheon education posting as freshly collected.
    regional = unified.get("regionalPublication")
    required = REQUIRED_PROVINCES
    if regional is not None:
        if not isinstance(regional, dict) or (
            regional.get("policy") != "seoul-gyeonggi-isolated-verified-v1"
            or regional.get("state") != "verified"
            or regional.get("refreshedRegions") != ["경기", "서울"]
            or int(regional.get("refreshedOfficialSourceCount") or 0) != 38
            or (regional.get("heldRegions") or {}).get("인천", {}).get("state") != "stale"
        ):
            raise SystemExit("invalid regional publication proof; Incheon hold not trusted")
        required = {"경기", "서울"}
        held_education = [
            row for row in official_rows
            if row.get("sourceSurface") == "official" and "인천" in provinces(row)
        ]
        if held_education:
            raise SystemExit(f"stale Incheon education posts leaked into regional publication: {len(held_education)}")
    missing_published = required - published
    if missing_published:
        raise SystemExit(
            f"unified official publication missing mandatory provinces: {sorted(missing_published)}"
        )

    print(
        "mandatory metro publication verified:",
        sorted(required),
        f"officialSources={expected_sources}",
        f"officialRows={len(official_rows)}",
    )


if __name__ == "__main__":
    main()
