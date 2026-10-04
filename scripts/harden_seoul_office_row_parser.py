#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRAPER = ROOT / "scripts" / "scrape_jobs.py"
COVERAGE = ROOT / "scripts" / "complete_support_coverage.py"

SCRAPER_HELPER_MARKER = "def seoul_support_title(vals, detail_anchor=None, anchors=()):"
SCRAPER_HELPER = r'''

def seoul_support_title(vals, detail_anchor=None, anchors=()):
    """Prefer SEN subject columns over duplicated detail anchors for the visible title."""
    placeholders = {"", "-", "--", "해당없음", "없음"}
    parts = []
    for key in ("분야1", "분야2"):
        value = clean(first_of(vals, [key]))
        if value not in placeholders and value not in parts:
            parts.append(value)
    if parts:
        return " ".join(parts)

    explicit = clean(first_of(vals, ["제목", "공고명"]))
    if explicit not in placeholders:
        return explicit

    if detail_anchor is not None:
        linked = clean(detail_anchor.get_text(" ", strip=True))
        if linked not in placeholders:
            return linked

    candidates = [clean(a.get_text(" ", strip=True)) for a in (anchors or [])]
    candidates = [x for x in candidates if x not in placeholders]
    return max(candidates, key=len, default="")
'''

COVERAGE_HELPER_MARKER = "def seoul_support_title(vals, fallback=\"\"):"
COVERAGE_HELPER = r'''

def seoul_support_title(vals, fallback=""):
    """Derive the SEN posting title from labelled subject cells before link text."""
    placeholders = {"", "-", "--", "해당없음", "없음"}
    parts = []
    for key in ("분야1", "분야2"):
        value = clean(first_of(vals, [key]))
        if value not in placeholders and value not in parts:
            parts.append(value)
    if parts:
        return " ".join(parts)

    explicit = clean(first_of(vals, ["제목", "공고명"]))
    if explicit not in placeholders:
        return explicit

    fallback = clean(fallback)
    return "" if fallback in placeholders else fallback
'''

SCRAPER_INSERT = "def scrape_seoul_office(src):\n"
COVERAGE_INSERT = "def seoul_items(soup, board, detail_registration):\n"

SCRAPER_OLD_TITLE = '''                vals=seoul_row_values(table,tr)\n                detail_anchor=seoul_detail_anchor_for_seq(tr,seq)\n                anchors=[a for a in tr.find_all("a") if clean(a.get_text(" ",strip=True))]\n                title=clean(detail_anchor.get_text(" ",strip=True) if detail_anchor else "")\n                if not title:\n                    title=first_of(vals,["제목","공고명"])\n                if not title:\n                    title=clean(max((a.get_text(" ",strip=True) for a in anchors),key=len,default=""))\n                if len(title)<3 or EXCLUDE_WORDS.search(title): continue\n'''
SCRAPER_NEW_TITLE = '''                vals=seoul_row_values(table,tr)\n                detail_anchor=seoul_detail_anchor_for_seq(tr,seq)\n                anchors=[a for a in tr.find_all("a") if clean(a.get_text(" ",strip=True))]\n                title=seoul_support_title(vals,detail_anchor,anchors)\n                if not title or EXCLUDE_WORDS.search(title):\n                    parse_incomplete += 1\n                    continue\n'''

SCRAPER_OLD_SUBJECT = '''                subject_parts=[first_of(vals,["분야1"]),first_of(vals,["분야2"])]\n                subject=" / ".join(x for x in subject_parts if x) or first_of(vals,["분야(과목)","분야","과목"])\n'''
SCRAPER_NEW_SUBJECT = '''                subject_parts=[clean(first_of(vals,["분야1"])),clean(first_of(vals,["분야2"]))]\n                subject_parts=[x for x in subject_parts if x and x not in {"-","--","해당없음","없음"}]\n                subject=" / ".join(dict.fromkeys(subject_parts)) or first_of(vals,["분야(과목)","분야","과목"])\n'''

COVERAGE_OLD_TITLE = '''            vals = seoul_values(table, tr)\n            title = seoul_detail_title(tr, seq) or first_of(vals, ["제목", "공고명"])\n            school = first_of(vals, ["학교명", "기관명", "작성자"])\n'''
COVERAGE_NEW_TITLE = '''            vals = seoul_values(table, tr)\n            title = seoul_support_title(vals, seoul_detail_title(tr, seq))\n            school = first_of(vals, ["학교명", "기관명", "작성자"])\n'''


def insert_before_once(text, marker, insert, label):
    if marker in text:
        return text
    if insert not in text:
        raise SystemExit(f"{label}: insertion point missing")
    return text.replace(insert, marker + "\n" + insert, 1)


def replace_once(text, old, new, label):
    count = text.count(old)
    if count == 0 and new in text:
        return text
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one target, found {count}")
    return text.replace(old, new, 1)


def patch_scraper():
    text = SCRAPER.read_text(encoding="utf-8")
    original = text
    if SCRAPER_HELPER_MARKER not in text:
        if SCRAPER_INSERT not in text:
            raise SystemExit("scraper helper insertion point missing")
        text = text.replace(SCRAPER_INSERT, SCRAPER_HELPER + "\n" + SCRAPER_INSERT, 1)
    text = replace_once(text, SCRAPER_OLD_TITLE, SCRAPER_NEW_TITLE, "scraper title parser")
    text = replace_once(text, SCRAPER_OLD_SUBJECT, SCRAPER_NEW_SUBJECT, "scraper subject parser")
    compile(text, str(SCRAPER), "exec")
    if text != original:
        SCRAPER.write_text(text, encoding="utf-8")
        return True
    return False


def patch_coverage():
    text = COVERAGE.read_text(encoding="utf-8")
    original = text
    if COVERAGE_HELPER_MARKER not in text:
        if COVERAGE_INSERT not in text:
            raise SystemExit("coverage helper insertion point missing")
        text = text.replace(COVERAGE_INSERT, COVERAGE_HELPER + "\n" + COVERAGE_INSERT, 1)
    text = replace_once(text, COVERAGE_OLD_TITLE, COVERAGE_NEW_TITLE, "coverage title parser")
    compile(text, str(COVERAGE), "exec")
    if text != original:
        COVERAGE.write_text(text, encoding="utf-8")
        return True
    return False


def main():
    scraper_changed = patch_scraper()
    coverage_changed = patch_coverage()
    print(
        "Seoul support title parser hardened",
        f"scraper_changed={scraper_changed}",
        f"coverage_changed={coverage_changed}",
    )


if __name__ == "__main__":
    main()
