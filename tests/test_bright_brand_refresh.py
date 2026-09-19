from pathlib import Path

index = Path("index.html").read_text(encoding="utf-8")
css = Path("edujob-refresh.css").read_text(encoding="utf-8")
js = Path("edujob-refresh.js").read_text(encoding="utf-8")
logo = Path("edujob-logo.svg").read_text(encoding="utf-8")
mascot_png = Path("assets/mascot.png")

required_index = [
    "edujob-refresh.css?v=20260919g",
    "edujob-refresh.js?v=20260920b",
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
    "assets/mascot.png?v=20260920b",
    "radarAlertCard",
    "내 채용 레이더",
]
for needle in required_js:
    if needle not in js:
        raise SystemExit(f"bright refresh JS contract missing: {needle}")

if "#03c75a" in css.lower():
    raise SystemExit("legacy NAVER green must not return in bright refresh")

if "학사모 E 로고" not in logo:
    raise SystemExit("brand logo SVG accessibility label missing")
if not mascot_png.exists() or mascot_png.stat().st_size < 10000:
    raise SystemExit("final raster mascot asset missing or unexpectedly small")

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


mobile = Path("mobile-ui.js").read_text(encoding="utf-8")

if "\\n<link" in index or "</script>\\n<script" in index:
    raise SystemExit("literal backslash-n artifact must never render in the page")

if "nav.id='edujobTabs'" in mobile or 'nav.id="edujobTabs"' in mobile:
    raise SystemExit("legacy top scope tabs must not be recreated")

if "mobile-ui.js?v=20260919a" not in index:
    raise SystemExit("mobile cleanup must bust the legacy mobile-ui cache")

if "min-height:48px!important" not in css:
    raise SystemExit("mobile radar metric cards must stay extra compact")

print("mobile cleanup v3 contract verified")



radar = Path("job-radar.js").read_text(encoding="utf-8")

if "grid-template-columns:repeat(4,minmax(0,1fr))!important" not in css:
    raise SystemExit("mobile radar must be a one-row four-column strip")

for short in ['data-short="신규"', 'data-short="관심"', 'data-short="일치"']:
    if short not in radar:
        raise SystemExit(f"mobile radar short label missing: {short}")

if "edujob-logo.svg?v=20260919g" not in js or "assets/mascot.png?v=20260920b" not in js:
    raise SystemExit("brand asset cache busting is required")

print("mobile radar strip v5 and SVG cache-bust contract verified")


if "min-height:56px!important" not in css or "#statusHeading h2" not in css:
    raise SystemExit("stats compact v6 contract missing")

if "M29 50 90 23l67 25-64 29z" not in logo:
    raise SystemExit("logo cap must be visibly oversized and worn")

if "edujob-logo.svg?v=20260919g" not in js or "assets/mascot.png?v=20260920b" not in js:
    raise SystemExit("v6 brand asset cache busting missing")

print("stats compact v6 and oversized worn-cap contract verified")


if "grid-template-columns:repeat(4,minmax(0,1fr))!important" not in css:
    raise SystemExit("one-row recruitment stats v7 missing")

if "min-height:50px!important" not in css:
    raise SystemExit("recruitment stats must stay compact on mobile")

if 'translate(-8 -18) rotate(-4 91 58)' not in logo:
    raise SystemExit("logo cap offset must lightly overlap the E")

print("one-row recruitment stats v7 and raster mascot contract verified")
