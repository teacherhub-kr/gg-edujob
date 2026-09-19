#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_unified_search as build


def assert_music_category(row, label):
    projected = build.project_official(row)
    assert "음악·예체능" in projected["categories"], (label, projected["categories"])


assert_music_category(
    {
        "id": "fixture-title-music",
        "province": "경기",
        "school": "운암고등학교",
        "title": "운암고등학교 기간제 교사(음악) 채용 공고",
        "subject": "",
        "type": "기간제교원",
        "sourceType": "통합게시판",
    },
    "music in title",
)

assert_music_category(
    {
        "id": "fixture-subject-music",
        "province": "서울",
        "school": "예시중학교",
        "title": "2026학년도 기간제교원 채용 공고",
        "subject": "음악",
        "type": "기간제교원",
        "sourceType": "통합게시판",
    },
    "music in subject",
)

non_music = build.project_official(
    {
        "id": "fixture-math",
        "province": "경기",
        "school": "예시고등학교",
        "title": "2026학년도 기간제교원 채용 공고",
        "subject": "수학",
        "type": "기간제교원",
        "sourceType": "통합게시판",
    }
)
assert "음악·예체능" not in non_music["categories"], non_music["categories"]

print("official music category projection verified")
