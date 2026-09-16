#!/usr/bin/env python3
"""Fail closed unless Seoul, Gyeonggi and Incheon are all registered and published."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from source_registry import official_source_count

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {
    "gyeonggi": "경기",
    "seoul": "서울",
    "incheon": "인천",
}


def load(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def main() -> None:
    registry = load("sources.json")
    payload = load("jobs.json")
    jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
    status = payload.get("sources", {}) if isinstance(payload, dict) else {}

    missing_registry = []
    unhealthy = []
    counts = {}
    for key, label in REQUIRED.items():
        group = registry.get(key) if isinstance(registry, dict) else None
        central = group.get("central") if isinstance(group, dict) else None
        if not isinstance(central, dict) or not str(central.get("url") or "").startswith("https://"):
            missing_registry.append(label)
            continue

        runtime = ((status.get(key) or {}).get("central") or {}) if isinstance(status, dict) else {}
        count = int(runtime.get("count") or 0)
        counts[key] = count
        if runtime.get("ok") is not True or count <= 0:
            unhealthy.append(f"{label}:count={count},ok={runtime.get('ok')}")

    if missing_registry:
        raise SystemExit("Required official region absent from registry: " + ", ".join(missing_registry))
    if unhealthy:
        raise SystemExit("Required official central source is not healthy: " + "; ".join(unhealthy))

    expected_sources = official_source_count()
    published_sources = int(payload.get("officialSourceCount") or 0)
    if published_sources != expected_sources:
        raise SystemExit(
            f"Published official source count differs from registry: published={published_sources}, registry={expected_sources}"
        )

    incheon = [
        job for job in jobs
        if job.get("province") == "인천" and job.get("source") == "인천광역시교육청 채용공고"
    ]
    if not incheon:
        raise SystemExit("Incheon official source is registered but no Incheon jobs are present in jobs.json")

    malformed = []
    for job in incheon[:100]:
        raw = str(job.get("url") or "")
        parsed = urlparse(raw)
        query = parse_qs(parsed.query)
        ntt = str((query.get("nttSn") or [""])[0])
        if (
            parsed.scheme != "https"
            or not (parsed.hostname or "").endswith("ice.go.kr")
            or not parsed.path.endswith("/selectNttInfo.do")
            or not ntt.isdigit()
        ):
            malformed.append(raw)
            if len(malformed) >= 5:
                break
    if malformed:
        raise SystemExit(f"Incheon official detail-link identity malformed: {malformed}")

    print(json.dumps({
        "requiredRegions": list(REQUIRED),
        "registryOfficialSources": expected_sources,
        "runtimeCentralCounts": counts,
        "incheonPublishedJobs": len(incheon),
        "state": "ok",
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
