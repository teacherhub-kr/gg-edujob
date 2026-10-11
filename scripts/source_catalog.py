#!/usr/bin/env python3
"""Unified, read-only source catalog for metropolitan Edujob operations.

This module does not replace the existing collector registries yet.  It gives
the supervisor/CI one canonical view across:
- official education sources (sources.json)
- public cultural-foundation sources (cultural_foundation_registry.json)
- supplemental public/private sources (private_source_registry.py)
- onboarding candidates that are not publication-enabled yet

The catalog is deliberately read-only so workflow consolidation can be proven
before any collection path is retired.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from private_source_registry import PRIVATE_SOURCES
from source_registry import official_source_breakdown

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_OFFICIAL_BREAKDOWN = {"gyeonggi": 26, "seoul": 12, "incheon": 6}
EXPECTED_FOUNDATION_BREAKDOWN = {"서울": 24, "경기": 25, "인천": 6}
SUPPLEMENTAL_CLASS = {
    "lessoninfo": "private-discovery",
    "jobteacher": "private-discovery",
    "artmore": "private-discovery",
    "gonggonggangsa": "private-discovery",
    "cleaneye": "public-aggregator",
    "seekle": "public-institution",
    "boramyc": "public-institution",
}
ONBOARDING_CANDIDATES = (
    {
        "key": "hunjang",
        "name": "훈장마을",
        "sourceClass": "private-discovery",
        "status": "candidate",
    },
    {
        "key": "public-instructor",
        "name": "공공 강사·교육기관 후보군",
        "sourceClass": "public-institution",
        "status": "candidate",
    },
)


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def official_catalog() -> list[dict]:
    data = load_json(ROOT / "sources.json")
    rows: list[dict] = []
    for region_key, group in data.items():
        region_name = str(group.get("name") or region_key)
        central = group.get("central")
        if central:
            rows.append(
                {
                    "key": f"education:{region_key}:central",
                    "name": central.get("name") or region_name,
                    "region": region_name,
                    "sourceClass": "official-education",
                    "operatorType": "public",
                    "status": "production",
                    "url": central.get("url") or "",
                }
            )
        for office in group.get("supportOffices") or []:
            rows.append(
                {
                    "key": f"education:{region_key}:support:{office.get('name')}",
                    "name": office.get("name") or "",
                    "region": region_name,
                    "sourceClass": "official-education",
                    "operatorType": "public",
                    "status": "production",
                    "url": office.get("boardUrl") or office.get("url") or "",
                }
            )
    return rows


def foundation_catalog() -> list[dict]:
    data = load_json(ROOT / "cultural_foundation_registry.json")
    rows = []
    for foundation in data.get("institutions") or []:
        if foundation.get("enabled") is False:
            continue
        official_url = str(foundation.get("officialRecruitmentUrl") or "")
        rows.append(
            {
                "key": foundation.get("id") or "",
                "name": foundation.get("name") or "",
                "region": foundation.get("region") or "",
                "municipality": foundation.get("municipality") or "",
                "sourceClass": "public-foundation",
                "operatorType": "public",
                "status": "production-direct" if official_url else "registry-only",
                "url": official_url,
            }
        )
    return rows


def supplemental_catalog() -> list[dict]:
    rows = []
    for spec in PRIVATE_SOURCES:
        key = str(spec.get("key") or "")
        source_class = SUPPLEMENTAL_CLASS.get(key, "unclassified")
        rows.append(
            {
                "key": key,
                "name": spec.get("name") or key,
                "sourceClass": source_class,
                "operatorType": "public" if source_class.startswith("public-") else "private",
                "status": "production",
                "jobs": spec.get("jobs") or "",
                "report": spec.get("report") or "",
            }
        )
    return rows


def build_catalog() -> dict:
    official = official_catalog()
    foundations = foundation_catalog()
    supplemental = supplemental_catalog()
    return {
        "schemaVersion": 2,
        "scope": ["서울", "경기", "인천"],
        "officialEducation": official,
        "publicFoundations": foundations,
        "supplemental": supplemental,
        "onboardingCandidates": list(ONBOARDING_CANDIDATES),
        "counts": {
            "officialEducation": len(official),
            "publicFoundations": len(foundations),
            "publicFoundationsDirect": sum(1 for row in foundations if row["status"] == "production-direct"),
            "supplemental": len(supplemental),
            "onboardingCandidates": len(ONBOARDING_CANDIDATES),
        },
    }


def validate_catalog(catalog: dict) -> list[str]:
    failures: list[str] = []

    breakdown = official_source_breakdown()
    if breakdown != EXPECTED_OFFICIAL_BREAKDOWN:
        failures.append(f"official source breakdown changed: {breakdown}")
    if catalog["counts"]["officialEducation"] != 44:
        failures.append(f"official education source count must remain 44: {catalog['counts']['officialEducation']}")

    foundations = catalog["publicFoundations"]
    ids = [str(row.get("key") or "") for row in foundations]
    if len(foundations) != 55:
        failures.append(f"foundation registry must contain 55 enabled institutions: {len(foundations)}")
    if len(ids) != len(set(ids)) or not all(ids):
        failures.append("foundation registry IDs must be non-empty and unique")
    foundation_breakdown: dict[str, int] = {}
    for row in foundations:
        foundation_breakdown[row["region"]] = foundation_breakdown.get(row["region"], 0) + 1
        url = str(row.get("url") or "")
        if url and not url.startswith(("https://", "http://")):
            failures.append(f"invalid foundation recruitment URL: {row['key']}={url}")
    if foundation_breakdown != EXPECTED_FOUNDATION_BREAKDOWN:
        failures.append(f"foundation region breakdown changed: {foundation_breakdown}")
    if catalog["counts"]["publicFoundationsDirect"] != 55:
        failures.append(
            f"public foundation direct coverage must remain 55: {catalog['counts']['publicFoundationsDirect']}"
        )

    supplemental = catalog["supplemental"]
    keys = [str(row.get("key") or "") for row in supplemental]
    if set(keys) != set(SUPPLEMENTAL_CLASS):
        failures.append(f"supplemental source set changed without catalog classification: {sorted(keys)}")
    unclassified = [row["key"] for row in supplemental if row.get("sourceClass") == "unclassified"]
    if unclassified:
        failures.append(f"unclassified supplemental sources: {unclassified}")

    candidate_keys = {row["key"] for row in catalog["onboardingCandidates"]}
    if candidate_keys != {"hunjang", "public-instructor"}:
        failures.append(f"unexpected onboarding candidate set: {sorted(candidate_keys)}")

    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    catalog = build_catalog()
    failures = validate_catalog(catalog)
    summary = {
        "schemaVersion": catalog["schemaVersion"],
        "scope": catalog["scope"],
        "counts": catalog["counts"],
        "officialBreakdown": official_source_breakdown(),
        "supplementalClasses": {row["key"]: row["sourceClass"] for row in catalog["supplemental"]},
        "onboardingCandidates": [row["key"] for row in catalog["onboardingCandidates"]],
        "valid": not failures,
        "failures": failures,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.validate and failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
