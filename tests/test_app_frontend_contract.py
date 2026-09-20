from pathlib import Path

html=Path("app.html").read_text(encoding="utf-8")
css=Path("app.css").read_text(encoding="utf-8")
js=Path("app.js").read_text(encoding="utf-8")
store=Path("user-store.js").read_text(encoding="utf-8")
alerts=Path("alert-client.js").read_text(encoding="utf-8")

for needle in ["app.css","user-store.js","app.js","direct-link-guard.js","alert-client.js","#/home","#/search","#/radar","#/saved","#/me"]:
    if needle not in html:
        raise SystemExit(f"app shell contract missing: {needle}")

for legacy in ["edujob-final-ui.css","edujob-refresh.css","mobile-ui.js","metro-ui.js","naver-theme.css","unified-ui.js"]:
    if legacy in html:
        raise SystemExit(f"preview app must not load legacy UI layer: {legacy}")

for needle in ["--brand:#2B7CF3","--page-bg:#EFF5FF",".bottom-nav",".job-card",".filter-drawer",".home-radar"]:
    if needle not in css:
        raise SystemExit(f"design token/component missing: {needle}")

for needle in [
    "fetch('unified_jobs.json',{cache:'no-cache'})",
    "const PAGE_SIZE=80",
    "openMethod==='POST'",
    "sourceSurfaceLabel",
    "regionsOf",
    "마감일 미정",
    "store()?.recent",
    "resetLocal",
    "location.hash",
    "registeredLabel",
]:
    if needle not in js:
        raise SystemExit(f"app behavior contract missing: {needle}")

if "jobs.json" in js.replace("unified_jobs.json",""):
    raise SystemExit("new frontend must not fetch jobs.json")

for needle in ["recent:'edujob.recentJobs.v1'","recent:{","resetLocal:"]:
    if needle not in store:
        raise SystemExit(f"user store extension missing: {needle}")

print("frontend rebuild preview contract verified")


# Approved mockup parity guards
for needle in [
    "마감임박",
    "radar-heading-icon",
    'class="job-deadline"',
    'class="results-sort"',
    'class="hero-title-row"',
    'class="empty-cta"',
    "menu-list menu-list-single",
]:
    if needle not in js and needle not in css:
        raise SystemExit(f"approved mockup parity contract missing: {needle}")

if "D-" + "$" + "{d}" in js:
    raise SystemExit("deadline badge must use vocabulary '마감임박', not D-day text")

card_start=js.find("const cardHtml")
card_end=js.find("const jobsListHtml", card_start)
card_block=js[card_start:card_end]
if 'meta-chip">${esc(deadline)}' in card_block:
    raise SystemExit("deadline must not be rendered as a fourth meta chip")

search_start=js.find("const searchHtml")
search_end=js.find("const profileSummary", search_start)
search_block=js[search_start:search_end]
filter_row=search_block.split('${filterDrawerHtml()}')[0]
if 'id="sortSelect"' in filter_row:
    raise SystemExit("sort control must live on results row, not filter row")

if "edujob-final-ui.css" in html or "edujob-final-ui.js" in html:
    raise SystemExit("canonical app preview must not load the legacy final-ui layer")


# Readable six-step type scale and density guards
for needle in [
    "--fs-xs:11px",
    "--fs-sm:12px",
    "--fs-md:13px",
    "--fs-lg:15px",
    "--fs-xl:16px",
    "--fs-2xl:18px",
]:
    if needle not in css:
        raise SystemExit(f"type scale variable missing: {needle}")

import re
allowed = {
    "var(--fs-xs)",
    "var(--fs-sm)",
    "var(--fs-md)",
    "var(--fs-lg)",
    "var(--fs-xl)",
    "var(--fs-2xl)",
}
font_sizes = re.findall(r"font-size:\s*([^;}\n]+)", css)
bad_font_sizes = [v.strip() for v in font_sizes if v.strip() not in allowed]
if bad_font_sizes:
    raise SystemExit(f"font-size must use six-step variables only: {bad_font_sizes[:10]}")

if re.search(r"(?:^|[;{\n])\s*font:\s*[^;}\n]*\d+(?:\.\d+)?px", css):
    raise SystemExit("font shorthand must not contain direct pixel font sizes")

for needle in [
    ".job-meta{display:flex;align-items:center;gap:6px;min-width:0}",
    "padding-bottom:calc(57px + env(safe-area-inset-bottom, 0px) + 16px)",
    ".school-emblem{width:40px;height:40px}",
    "font-size:var(--fs-lg);\n  line-height:1.3;",
]:
    if needle not in css:
        raise SystemExit(f"density/safe-area contract missing: {needle}")

card_start=js.find("const cardHtml")
card_end=js.find("const jobsListHtml", card_start)
card_block=js[card_start:card_end]
if 'class="job-meta"' not in card_block:
    raise SystemExit("deadline/meta must share the same compact row")
if card_block.find('class="job-deadline"') < card_block.find('class="job-meta"'):
    raise SystemExit("deadline must render inside the meta row")


# Final mascot asset guards
import hashlib
for path in list(Path(".").rglob("*.html")) + list(Path(".").rglob("*.js")) + list(Path(".").rglob("*.css")):
    try:
        txt=path.read_text(encoding="utf-8")
    except Exception:
        continue
    legacy_mascot = "edujob-mascot" + ".svg"
    if legacy_mascot in txt:
        raise SystemExit(f"legacy mascot SVG reference remains in code: {path}")

if "assets/mascot.png?v=20260920b" not in js:
    raise SystemExit("canonical app must use the final mascot cache version")

asset=Path("assets/mascot.png")
if not asset.exists():
    raise SystemExit("final mascot PNG is missing")
digest=hashlib.sha256(asset.read_bytes()).hexdigest()
if digest != "0a0c793bfb460bb9d02897b1f2f9219b561ef243221967f49c8095ff4ae5ccff":
    raise SystemExit(f"unexpected mascot asset bytes: {digest}")


# Original full checkbox filter is the canonical preview behavior.
for needle in [
    "const GYEONGGI_REGIONS",
    "const SEOUL_REGIONS",
    "const INCHEON_REGIONS",
    "미추홀구",
    "강화군",
    "옹진군",
    "공고 구분",
    "구인 분야",
    "과목·담당",
    "기간제교원",
    "data-region-all",
    "selectedSummaryHtml",
]:
    if needle not in js:
        raise SystemExit(f"full checkbox filter contract missing: {needle}")

for region in ["중구","동구","미추홀구","연수구","남동구","부평구","계양구","서구","강화군","옹진군"]:
    if region not in js:
        raise SystemExit(f"Incheon district missing: {region}")

for bad in [
    "  $('[data-filter]',screen).forEach",
    "  $('[data-region-all]',screen).forEach",
]:
    if bad in js:
        raise SystemExit(f"single-element selector used with forEach: {bad}")

for good in [
    "$$('[data-filter]',screen).forEach",
    "$$('[data-region-all]',screen).forEach",
]:
    if good not in js:
        raise SystemExit(f"checkbox binding missing: {good}")

if "quickFilterPanelHtml" in js:
    raise SystemExit("compact one-at-a-time quick filter must not replace the original full filter")

for needle in [
    ".check-grid.region-checks",
    ".filter-drawer-head",
    ".selected-box.show",
    ".radar-mascot img",
    ".radar-mascot span",
]:
    if needle not in css:
        raise SystemExit(f"restored filter/mascot layout CSS missing: {needle}")

if "left:0;" not in css or "left:62px;" not in css:
    raise SystemExit("home radar must place mascot left and message right")


# Calm hierarchy: preserve every filter, reduce what is visible at once.
for needle in [
    "const filterSectionHtml",
    'class="filter-section"',
    'class="filter-footer"',
    'id="filterApply"',
    'class="metric-grid calm"',
    'class="radar-actions calm"',
    'class="home-status-strip"',
]:
    if needle not in js and needle not in css:
        raise SystemExit(f"calm hierarchy contract missing: {needle}")

home_start=js.find("const homeHtml")
home_end=js.find("const searchHtml", home_start)
home_block=js[home_start:home_end]
if "filterDrawerHtml()" in home_block:
    raise SystemExit("home must not expand the detailed filter drawer")
if "채용 현황" in home_block:
    raise SystemExit("home must not give the status dashboard equal visual weight to jobs")

filter_start=js.find("const filterDrawerHtml")
filter_end=js.find("const homeHtml", filter_start)
filter_block=js[filter_start:filter_end]
for label in ["시·도","지역","학교급","직종","공고 구분","구인 분야","과목·담당"]:
    if label not in filter_block:
        raise SystemExit(f"full filter option disappeared: {label}")

if "region-group" not in js or "region-group-body" not in js:
    raise SystemExit("long region lists must remain available in nested groups")


# Saved conditions must drive the home page after the user applies them.
for needle in [
    "const matches=p?[...profileMatches(p)]",
    "const homeRows=p?matches:latest",
    "내 저장 조건",
    "내 조건 맞춤 공고",
    "data-home-profile=\"edit\"",
    "data-home-profile=\"matches\"",
    "profileSignature",
    "store()?.profile?.set?.(next)",
]:
    if needle not in js:
        raise SystemExit(f"saved-condition home contract missing: {needle}")

# The filter must use real, tappable checkboxes and update the explicit checked class.
for needle in [
    "pointer-events:auto !important",
    "opacity:1 !important",
    "accent-color:#377bd7",
    ".check-chip.checked",
]:
    if needle not in css:
        raise SystemExit(f"native checkbox contract missing: {needle}")
if "class=\"check-chip ${set.has(v)?'checked':''}\"" not in js:
    raise SystemExit("checkbox checked class must render from filter state")
if "classList.toggle('checked',e.target.checked)" not in js:
    raise SystemExit("checkbox checked class must update immediately on change")

# New app alert toggle must call the push client directly, not a legacy DOM button.
for needle in [
    "window.EduJobAlerts",
    "await client.subscribe()",
    "await client.unsubscribe()",
]:
    if needle not in js:
        raise SystemExit(f"new app alert integration missing: {needle}")
if "jobRadarAlerts" in js:
    raise SystemExit("new app must not depend on the legacy alert button")
for needle in [
    "window.EduJobAlerts=Object.freeze",
    "supported,",
    "subscribe,",
    "unsubscribe,",
    "sync",
]:
    if needle not in alerts:
        raise SystemExit(f"alert client API missing: {needle}")


# No single-element selector may ever be iterated. This runtime bug halts bindScreen
# and makes every following screen control appear dead.
for line in js.splitlines():
    stripped=line.lstrip()
    if stripped.startswith("$(") and ".forEach" in stripped:
        raise SystemExit(f"single-element selector used with forEach: {stripped}")

for good in [
    "$$('[data-home]',screen).forEach",
    "$$('[data-home-profile]',screen).forEach",
]:
    if good not in js:
        raise SystemExit(f"home click binding missing: {good}")
