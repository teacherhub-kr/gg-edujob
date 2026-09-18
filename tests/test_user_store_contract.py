from pathlib import Path

store = Path("user-store.js").read_text(encoding="utf-8")
radar = Path("job-radar.js").read_text(encoding="utf-8")
index = Path("index.html").read_text(encoding="utf-8")

required = {
    "profile key": "edujob.jobRadar.profile.v1",
    "snapshot key": "edujob.jobRadar.snapshot.v1",
    "favorites key": "edujob.jobRadar.favorites.v1",
    "export state": "exportState",
    "import state": "importState",
    "account adapter": "setAccountAdapter",
    "remote hydrate": "hydrateAccount",
    "remote sync": "syncAccount",
    "local-to-account migration": "migrateLocalToAccount",
    "local mode": "storageMode",
}
missing = [label for label, needle in required.items() if needle not in store]
if missing:
    raise SystemExit("user-store account-ready contract missing: " + ", ".join(missing))

if "localStorage" in radar:
    raise SystemExit("job-radar.js must remain storage-provider agnostic")

if "const memory=new Map()" not in store:
    raise SystemExit("user store must keep an in-memory fallback when browser storage is unavailable")

store_pos = index.find('user-store.js')
radar_pos = index.find('job-radar.js')
if store_pos < 0 or radar_pos < 0 or store_pos >= radar_pos:
    raise SystemExit("user-store.js must load before job-radar.js")

print("account-ready user-store contract verified")
