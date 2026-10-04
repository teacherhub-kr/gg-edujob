#!/usr/bin/env python3
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "scripts" / "scrape_jobs.py"
text = path.read_text(encoding="utf-8")
old = '"subject":first_of(vals,["과목","분야"]),"region":region,"regions":regions,"type":guess_type(raw_type+" "+title+" "+subject),'
new = '"subject":first_of(vals,["과목","분야"]),"region":region,"regions":regions,"type":guess_type(raw_type+" "+title),'
if text.count(old) != 1:
    raise SystemExit(f"expected one accidental Gyeonggi edit, found {text.count(old)}")
text = text.replace(old, new, 1)
compile(text, str(path), "exec")
path.write_text(text, encoding="utf-8")
print("restored Gyeonggi type expression")
