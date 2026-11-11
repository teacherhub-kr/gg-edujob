from pathlib import Path

text = Path("job-radar.js").read_text(encoding="utf-8")
store = Path("user-store.js").read_text(encoding="utf-8")

required = {
    "favorites toggle": "toggleFavorite",
    "favorite-only state": "favoriteOnly",
    "favorite button": "job-favorite-btn",
    "new match badge": "내 신규",
    "new match emphasis": "has-new",
    "prevent posting navigation": "e.preventDefault();e.stopPropagation();",
    "favorites independent dataset": "const rows=(Array.isArray(jobs)?jobs:[]).filter",
    "store injection": "window.EduJobUserStore",
}

missing = [label for label, needle in required.items() if needle not in text and needle not in store]
if missing:
    raise SystemExit("job radar personalization contract missing: " + ", ".join(missing))

if "edujob.jobRadar.favorites.v1" not in store:
    raise SystemExit("legacy favorites key must remain stable for migration compatibility")

if "localStorage" in text:
    raise SystemExit("job-radar.js must not access localStorage directly; use user-store.js")

if "if(newOnly)favoriteOnly=false;" not in text:
    raise SystemExit("new-only and favorites modes must remain mutually exclusive")

if "if(favoriteOnly)newOnly=false;" not in text:
    raise SystemExit("favorites and new-only modes must remain mutually exclusive")

print("job radar personalization contract verified")

for needle in (
    "'사회·역사':/(^|\\s)(사회|역사|한국사|지리|윤리|도덕|통합사회)(\\s|$)/",
    "'국어':/(^|\\s)(국어|독서|논술)(\\s|$)/",
    "'과학':/(^|\\s)(과학|물리|화학|생명과학|생물|지구과학|통합과학)(\\s|$)/",
):
    if needle not in text:
        raise SystemExit("job radar subject contract drift: " + needle)
