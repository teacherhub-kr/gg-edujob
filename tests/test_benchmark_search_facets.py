#!/usr/bin/env python3
from pathlib import Path
import shutil
import subprocess

root = Path(__file__).resolve().parents[1]
ui_path = root / "unified-ui.js"
ui = ui_path.read_text(encoding="utf-8")

# Benchmark-derived facets must remain client-side and non-destructive.
assert "state.subjects=state.subjects||new Set();" in ui
assert "addFilterSection('subjectFilters','과목·담당'" in ui
for label in ("국어", "영어", "수학", "과학", "사회·역사", "음악", "미술", "체육", "특수", "보건", "상담", "사서", "영양", "정보·컴퓨터", "유아"):
    assert f"'{label}'" in ui, f"missing subject facet: {label}"
assert "state.subjects.size" in ui and "matchesSubject(j,s)" in ui

# Quick filters mirror useful official-portal affordances without hiding unknown-deadline jobs by default.
assert "state.quick=state.quick||'all';" in ui
assert "['all','전체']" in ui
assert "['today','오늘 등록']" in ui
assert "['soon3','3일 내 마감']" in ui
assert "state.quick==='today'&&!isToday(j.registered)" in ui
assert "state.quick==='soon3'" in ui and "d===null||d<0||d>3" in ui

# Reset must clear every benchmark-added facet so the feature cannot trap users in a hidden filter state.
assert "state.subjects.clear();state.quick='all'" in ui
assert "#sourceKindFilters input,#categoryFilters input,#subjectFilters input" in ui

# Catch syntax regressions when Node is available (GitHub hosted runners include it).
node = shutil.which("node")
if node:
    subprocess.run([node, "--check", str(ui_path)], check=True)

print("PASS benchmark search facets: subject filter + today/soon quick filters")
