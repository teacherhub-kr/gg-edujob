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
INCHOEN_REQUIRED_BOARDS = {
    "1981": "https://www.ice.go.kr/ice/na/ntt/selectNttList.do?bbsId=1981&mi=10997",
    "1534": "https://www.ice.go.kr/afterschool/na/ntt/selectNttList.do?bbsId=1534&mi=10571",
}
INCHEON_REQUIRED_SUPPORT = {
    "nambu": "인천남부교육지원청",
    "bukbu": "인천북부교육지원청",
    "dongbu": "인천동부교육지원청",
    "seobu": "인천서부교육지원청",
    "ganghwa": "인천강화교육지원청",
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

    incheon_group = registry.get("incheon") if isinstance(registry, dict) else None
    incheon_central = incheon_group.get("central") if isinstance(incheon_group, dict) else None
    registered_boards = {
        str(item.get("bbsId") or ""): str(item.get("url") or "")
        for item in ((incheon_central or {}).get("requiredBoards") or [])
        if isinstance(item, dict)
    }
    missing_incheon_boards = [
        bbs for bbs, url in INCHOEN_REQUIRED_BOARDS.items()
        if registered_boards.get(bbs) != url
    ]
    if missing_incheon_boards:
        missing_registry.append("인천 필수게시판:" + ",".join(missing_incheon_boards))

    support_registry = (incheon_group or {}).get("supportOffices") or []
    support_by_key = {
        str(item.get("key") or ""): item
        for item in support_registry
        if isinstance(item, dict)
    }
    missing_support = [
        key for key, name in INCHEON_REQUIRED_SUPPORT.items()
        if key not in support_by_key
        or support_by_key[key].get("name") != name
        or not str(support_by_key[key].get("url") or "").startswith("https://")
    ]
    if missing_support:
        missing_registry.append("인천 교육지원청:" + ",".join(missing_support))

    if missing_registry:
        raise SystemExit("Required official region/source absent from registry: " + ", ".join(missing_registry))
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

    present_bbs = {str(job.get("bbsId") or "") for job in incheon}
    missing_published_boards = sorted(set(INCHOEN_REQUIRED_BOARDS) - present_bbs)
    if missing_published_boards:
        raise SystemExit(
            "Incheon required official board has no published jobs: " + ", ".join(missing_published_boards)
        )

    runtime_incheon = ((status.get("incheon") or {}).get("central") or {}) if isinstance(status, dict) else {}
    health = runtime_incheon.get("boardHealth") or []
    healthy_bbs = {
        str(item.get("bbsId") or "")
        for item in health
        if isinstance(item, dict) and item.get("coverageComplete") is True
    }
    missing_runtime_proof = sorted(set(INCHOEN_REQUIRED_BOARDS) - healthy_bbs)
    if missing_runtime_proof:
        raise SystemExit(
            "Incheon required board lacks complete runtime traversal evidence: " + ", ".join(missing_runtime_proof)
        )

    runtime_support = ((status.get("incheon") or {}).get("supportOffices") or []) if isinstance(status, dict) else []
    runtime_support_by_name = {
        str(item.get("name") or ""): item
        for item in runtime_support
        if isinstance(item, dict)
    }
    unhealthy_support = []
    for _key, name in INCHEON_REQUIRED_SUPPORT.items():
        item = runtime_support_by_name.get(name)
        if not item or item.get("ok") is not True or item.get("coverageComplete") is not True:
            unhealthy_support.append(name)
    if unhealthy_support:
        raise SystemExit(
            "Incheon support-office runtime traversal is incomplete: " + ", ".join(unhealthy_support)
        )

    malformed = []
    for job in incheon[:200]:
        raw = str(job.get("url") or "")
        parsed = urlparse(raw)
        query = parse_qs(parsed.query)
        ntt = str((query.get("nttSn") or [""])[0])
        bbs = str(job.get("bbsId") or (query.get("bbsId") or [""])[0])
        if (
            parsed.scheme != "https"
            or not (parsed.hostname or "").endswith("ice.go.kr")
            or not parsed.path.endswith("/selectNttInfo.do")
            or not ntt.isdigit()
            or bbs not in INCHOEN_REQUIRED_BOARDS
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
        "incheonRequiredBoards": sorted(INCHOEN_REQUIRED_BOARDS),
        "incheonPublishedBoards": sorted(present_bbs & set(INCHOEN_REQUIRED_BOARDS)),
        "incheonSupportOffices": sorted(runtime_support_by_name),
        "state": "ok",
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
