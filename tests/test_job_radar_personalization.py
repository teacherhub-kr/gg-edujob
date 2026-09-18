from pathlib import Path

text = Path("job-radar.js").read_text(encoding="utf-8")

required = {
    "favorites storage key": "edujob.jobRadar.favorites.v1",
    "favorites toggle": "toggleFavorite",
    "favorite-only state": "favoriteOnly",
    "favorite button": "job-favorite-btn",
    "new match badge": "내 신규",
    "new match emphasis": "has-new",
    "prevent posting navigation": "e.preventDefault();e.stopPropagation();",
    "favorites independent dataset": "const rows=(Array.isArray(jobs)?jobs:[]).filter",
}

missing = [label for label, needle in required.items() if needle not in text]
if missing:
    raise SystemExit("job radar personalization contract missing: " + ", ".join(missing))

if "if(newOnly)favoriteOnly=false;" not in text:
    raise SystemExit("new-only and favorites modes must remain mutually exclusive")

if "if(favoriteOnly)newOnly=false;" not in text:
    raise SystemExit("favorites and new-only modes must remain mutually exclusive")

print("job radar personalization contract verified")
