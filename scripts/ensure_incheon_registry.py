#!/usr/bin/env python3
"""Ensure the required Incheon official recruitment source exists in sources.json.

This is an idempotent migration helper. The first verified Fast run after deployment writes the
source into the canonical registry; later runs only validate/normalize the same entry.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "sources.json"

INCHOEON = {
    "name": "인천",
    "central": {
        "name": "인천광역시교육청 채용공고",
        "url": "https://www.ice.go.kr/ice/na/ntt/selectNttList.do?bbsId=1981&mi=10997",
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
