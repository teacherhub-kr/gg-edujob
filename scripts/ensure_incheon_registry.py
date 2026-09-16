#!/usr/bin/env python3
"""Ensure the required Incheon official recruitment network exists in sources.json.

Incheon uses one logical regional source backed by two mandatory official boards:
1) the general education-office recruitment board; and
2) the Neulbom Support Center individual-contractor/external-instructor board.
The central board itself explicitly redirects after-school postings to the second board, so both
must be present before Incheon registry completeness can be claimed.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "sources.json"

CENTRAL_URL = "https://www.ice.go.kr/ice/na/ntt/selectNttList.do?bbsId=1981&mi=10997"
AFTERSCHOOL_URL = "https://www.ice.go.kr/afterschool/na/ntt/selectNttList.do?bbsId=1534&mi=10571"

INCHOEON = {
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
    "supportOffices": [],
}


def main() -> None:
    data = json.loads(PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("sources.json must be a JSON object")

    current = data.get("incheon")
    if current is not None and not isinstance(current, dict):
        raise SystemExit("Refusing to replace malformed incheon registry entry")

    changed = current != INCHOEON
    data["incheon"] = INCHOEON
    PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Incheon official registry:", "updated" if changed else "already current")


if __name__ == "__main__":
    main()
