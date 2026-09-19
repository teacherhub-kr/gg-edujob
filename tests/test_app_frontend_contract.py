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
    if "edujob-mascot.svg" in txt:
        raise SystemExit(f"legacy mascot SVG reference remains in code: {path}")

if "assets/mascot.png?v=20260920b" not in js:
    raise SystemExit("canonical app must use the final mascot cache version")

asset=Path("assets/mascot.png")
if not asset.exists():
    raise SystemExit("final mascot PNG is missing")
digest=hashlib.sha256(asset.read_bytes()).hexdigest()
if digest != "0a0c793bfb460bb9d02897b1f2f9219b561ef243221967f49c8095ff4ae5ccff":
    raise SystemExit(f"unexpected mascot asset bytes: {digest}")
