from pathlib import Path

html=Path("app.html").read_text(encoding="utf-8")
css=Path("app.css").read_text(encoding="utf-8")
js=Path("app.js").read_text(encoding="utf-8")
store=Path("user-store.js").read_text(encoding="utf-8")

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
