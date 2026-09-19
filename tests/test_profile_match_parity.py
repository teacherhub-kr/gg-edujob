#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "scripts"))
from build_unified_search import categories

assert "음악·예체능" in categories(
    "2026학년도 기간제교원(음악) 채용 공고",
    "official",
    "공식 채용",
), "generic official music title must classify as 음악·예체능"

ui = (root / "unified-ui.js").read_text(encoding="utf-8")
radar = (root / "job-radar.js").read_text(encoding="utf-8")
alerts = (root / "supabase/functions/_shared/alerts.ts").read_text(encoding="utf-8")

canonical = [
    "국어","영어","수학","과학","사회·역사","음악","미술","체육",
    "특수","보건","상담","사서","영양","정보·컴퓨터","유아",
]
for label in canonical:
    needle = f"'{label}':"
    assert needle in ui, f"unified UI missing {label}"
    assert needle in radar, f"radar missing {label}"
    assert needle in alerts, f"push matcher missing {label}"

social = "'사회·역사':/(^|\\s)(사회|역사|한국사|지리|윤리|도덕|통합사회)(\\s|$)/"
assert social in radar
assert social in alerts

for text in (radar, alerts):
    assert "'국어':/(^|\\s)(국어|독서|논술)(\\s|$)/" in text
    assert "'영어':/(^|\\s)(영어|영어회화)(\\s|$)/" in text
    assert "'수학':/(^|\\s)(수학|수리)(\\s|$)/" in text
    assert "'과학':/(^|\\s)(과학|물리|화학|생명과학|생물|지구과학|통합과학)(\\s|$)/" in text

print("profile matching parity contract verified")
