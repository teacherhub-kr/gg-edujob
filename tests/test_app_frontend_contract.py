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
