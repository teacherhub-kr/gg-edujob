#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRAPER = ROOT / "scripts" / "scrape_jobs.py"
COVERAGE = ROOT / "scripts" / "complete_support_coverage.py"

SCRAPER_HELPER_MARKER = "def seoul_title_from_values(vals):"
SCRAPER_HELPERS = r'''

def _seoul_field_parts(vals):
    placeholders = {"", "-", "--", "해당없음", "없음"}
    parts = []
    for key in ("분야1", "분야2"):
        value = clean(first_of(vals, [key]))
        if value not in placeholders and value not in parts:
            parts.append(value)
    return parts


def seoul_title_from_values(vals):
    """Build a SEN visible title from labelled subject fields before repeated anchors."""
    parts = _seoul_field_parts(vals)
    if parts:
        return " ".join(parts)
    title = clean(first_of(vals, ["제목", "공고명"]))
    return "" if title in {"", "-", "--", "해당없음", "없음"} else title


def seoul_subject_from_values(vals):
    """Preserve short subjects and combine 분야1/분야2 without placeholder values."""
    parts = _seoul_field_parts(vals)
    if parts:
        return " / ".join(parts)
    subject = clean(first_of(vals, ["분야(과목)", "분야", "과목"]))
    return "" if subject in {"", "-", "--", "해당없음", "없음"} else subject
'''

COVERAGE_HELPER_MARKER = "def seoul_title_from_values(vals):"
COVERAGE_HELPERS = r'''

def seoul_title_from_values(vals):
    """Independently derive a SEN title from labelled 분야 fields, not anchor order."""
    placeholders = {"", "-", "--", "해당없음", "없음"}
    parts = []
    for key in ("분야1", "분야2"):
        value = clean(first_of(vals, [key]))
        if value not in placeholders and value not in parts:
            parts.append(value)
    if parts:
        return " ".join(parts)
    explicit = clean(first_of(vals, ["제목", "공고명"]))
    return "" if explicit in placeholders else explicit
'''

SCRAPER_INSERT = "def scrape_seoul_office(src):\n"
COVERAGE_INSERT = "def seoul_items(soup, board, detail_registration):\n"

SCRAPER_OLD_TITLE = '''                vals=seoul_row_values(table,tr)\n                detail_anchor=seoul_detail_anchor_for_seq(tr,seq)\n                anchors=[a for a in tr.find_all("a") if clean(a.get_text(" ",strip=True))]\n                title=clean(detail_anchor.get_text(" ",strip=True) if detail_anchor else "")\n                if not title:\n                    title=first_of(vals,["제목","공고명"])\n                if not title:\n                    title=clean(max((a.get_text(" ",strip=True) for a in anchors),key=len,default=""))\n                if len(title)<3 or EXCLUDE_WORDS.search(title): continue\n'''
SCRAPER_NEW_TITLE = '''                vals=seoul_row_values(table,tr)\n                detail_anchor=seoul_detail_anchor_for_seq(tr,seq)\n                anchors=[a for a in tr.find_all("a") if clean(a.get_text(" ",strip=True))]\n                title=seoul_title_from_values(vals)\n                if not title and detail_anchor:\n                    title=clean(detail_anchor.get_text(" ",strip=True))\n                if not title or title in {"-","--","해당없음","없음"}:\n                    title=clean(max((a.get_text(" ",strip=True) for a in anchors if clean(a.get_text(" ",strip=True)) not in {"-","--","해당없음","없음"}),key=len,default=""))\n                if not title or EXCLUDE_WORDS.search(title):\n                    parse_incomplete += 1\n                    continue\n'''

SCRAPER_OLD_SUBJECT = '''                subject_parts=[first_of(vals,["분야1"]),first_of(vals,["분야2"])]\n                subject=" / ".join(x for x in subject_parts if x) or first_of(vals,["분야(과목)","분야","과목"])\n'''
SCRAPER_NEW_SUBJECT = '''                subject=seoul_subject_from_values(vals)\n'''

COVERAGE_OLD_TITLE = '''            vals = seoul_values(table, tr)\n            title = seoul_detail_title(tr, seq) or first_of(vals, ["제목", "공고명"])\n            school = first_of(vals, ["학교명", "기관명", "작성자"])\n'''
COVERAGE_NEW_TITLE = '''            vals = seoul_values(table, tr)\n            title = seoul_title_from_values(vals) or seoul_detail_title(tr, seq)\n            school = first_of(vals, ["학교명", "기관명", "작성자"])\n'''


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
        text = text.replace(SCRAPER_INSERT, SCRAPER_HELPERS + "\n" + SCRAPER_INSERT, 1)
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
        text = text.replace(COVERAGE_INSERT, COVERAGE_HELPERS + "\n" + COVERAGE_INSERT, 1)
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
