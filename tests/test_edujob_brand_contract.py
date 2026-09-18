from pathlib import Path

index = Path("index.html").read_text(encoding="utf-8").lower()
theme = Path("edujob-theme.css").read_text(encoding="utf-8").lower()

if "naver-theme.css" in index:
    raise SystemExit("legacy naver-theme.css must not be loaded")

if "edujob-theme.css" not in index:
    raise SystemExit("edujob-theme.css must be loaded")

if "#03c75a" in theme:
    raise SystemExit("NAVER Green #03c75a must not be used in the Edujob theme")

required = {
    "independent brand color": "--brand:#17324d",
    "independent accent color": "--accent:#2f66d7",
    "independent logo": "content:'e'",
    "distinct search control": ".searchbox:focus-within",
}
missing = [label for label, needle in required.items() if needle not in theme]
if missing:
    raise SystemExit("Edujob brand contract missing: " + ", ".join(missing))

print("independent Edujob brand contract verified")
