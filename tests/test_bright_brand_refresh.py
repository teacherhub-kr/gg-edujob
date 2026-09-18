from pathlib import Path

index = Path("index.html").read_text(encoding="utf-8")
css = Path("edujob-refresh.css").read_text(encoding="utf-8")
js = Path("edujob-refresh.js").read_text(encoding="utf-8")
logo = Path("edujob-logo.svg").read_text(encoding="utf-8")
mascot = Path("edujob-mascot.svg").read_text(encoding="utf-8")

required_index = [
    "edujob-refresh.css?v=20260919b",
    "edujob-refresh.js?v=20260919b",
]
for needle in required_index:
    if needle not in index:
        raise SystemExit(f"bright refresh asset missing from index: {needle}")

required_css = [
    "--refresh-bg:#f6fbff",
    ".scope-chips",
    ".job-radar",
    ".radar-mascot-wrap",
    ".edujob-mobile-nav",
    "background:linear-gradient(135deg,#218cff,#0757df)",
]
for needle in required_css:
    if needle not in css:
        raise SystemExit(f"bright refresh CSS contract missing: {needle}")

required_js = [
    "학교·교육청",
    "학원·민간",
    "edujob-mascot.svg",
    "radarAlertCard",
    "내 채용 레이더",
]
for needle in required_js:
    if needle not in js:
        raise SystemExit(f"bright refresh JS contract missing: {needle}")

if "#03c75a" in css.lower():
    raise SystemExit("legacy NAVER green must not return in bright refresh")

if "학사모 E 로고" not in logo or "E 마스코트" not in mascot:
    raise SystemExit("brand SVG accessibility labels missing")

print("bright Edujob brand refresh contract verified")

mobile_polish = {
    "save label": "현재<br>조건<br>저장",
    "apply label": "내 조건<br>불러<br>오기",
    "new label": "새<br>공고",
    "favorite label": "♡<br>관심<br>공고",
    "compact mobile nav": ".edujob-mobile-nav button svg{width:18px!important;height:18px!important}",
    "short radar copy": "지난 방문 이후 신규 공고 0건",
}
combined = Path("job-radar.js").read_text(encoding="utf-8") + "\n" + css
for label, needle in mobile_polish.items():
    if needle not in combined:
        raise SystemExit(f"mobile polish contract missing: {label}")
