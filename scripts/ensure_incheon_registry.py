#!/usr/bin/env python3
"""Ensure the complete official Incheon recruitment network exists in sources.json.

Incheon has one metropolitan-office logical source backed by two mandatory citywide boards, plus
five education support offices: Nambu, Bukbu, Dongbu, Seobu and Ganghwa.

For Nambu and Seobu, only the official homepage is pinned because a stable recruitment-board path
has not been independently verified. Production discovers a recruitment link from the official
homepage and fails closed if it cannot prove one. We intentionally do not invent a guessed URL.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "sources.json"

CENTRAL_URL = "https://www.ice.go.kr/ice/na/ntt/selectNttList.do?bbsId=1981&mi=10997"
AFTERSCHOOL_URL = "https://www.ice.go.kr/afterschool/na/ntt/selectNttList.do?bbsId=1534&mi=10571"

SUPPORT_OFFICES = [
    {
        "key": "nambu",
        "name": "인천남부교육지원청",
        "url": "https://nambu.ice.go.kr/Main.do",
        "allowedHosts": ["nambu.ice.go.kr", "nambuice.go.kr"],
        "boardUrls": [],
        "autoDiscover": True,
    },
    {
        "key": "bukbu",
        "name": "인천북부교육지원청",
        "url": "https://bukbu.ice.go.kr/",
        "allowedHosts": ["bukbu.ice.go.kr"],
        "boardUrls": [
            "https://bukbu.ice.go.kr/bbs/data/list.do?bbs_mst_idx=BM0000000049&menu_idx=86"
        ],
        "autoDiscover": False,
    },
    {
        "key": "dongbu",
        "name": "인천동부교육지원청",
        "url": "https://dongbu.ice.go.kr/",
        "allowedHosts": ["dongbu.ice.go.kr"],
        "boardUrls": ["https://dongbu.ice.go.kr/participation/job_offer.jsp"],
        "autoDiscover": False,
    },
    {
        "key": "seobu",
        "name": "인천서부교육지원청",
        "url": "https://seobu.ice.go.kr/",
        "allowedHosts": ["seobu.ice.go.kr"],
        "boardUrls": [],
        "autoDiscover": True,
    },
    {
        "key": "ganghwa",
        "name": "인천강화교육지원청",
        "url": "https://ganghwa.ice.go.kr/",
        "allowedHosts": ["ganghwa.ice.go.kr"],
        "boardUrls": ["https://ganghwa.ice.go.kr/open/recruiting.asp"],
        "autoDiscover": False,
    },
]

INCHEON = {
    "name": "인천",
    "central": {
        "name": "인천광역시교육청 채용공고",
        "url": CENTRAL_URL,
        "requiredBoards": [
            {
                "name": "인천광역시교육청 채용공고",
                "url": CENTRAL_URL,
                "bbsId": "1981",
            },
            {
                "name": "인천광역시교육청 늘봄지원센터 개인위탁공고(외부강사)",
                "url": AFTERSCHOOL_URL,
                "bbsId": "1534",
            },
        ],
    },
    "supportOffices": SUPPORT_OFFICES,
}


def main() -> None:
    data = json.loads(PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("sources.json must be a JSON object")

    current = data.get("incheon")
    if current is not None and not isinstance(current, dict):
        raise SystemExit("Refusing to replace malformed incheon registry entry")

    changed = current != INCHEON
    data["incheon"] = INCHEON
    PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Incheon official registry:", "updated" if changed else "already current")


if __name__ == "__main__":
    main()
