#!/usr/bin/env python3
"""One-shot branch-only patcher for the 2026-10-04 Seoul support parser P0.

This file is deleted by the temporary branch workflow before the reviewed commit is
created. It exists only to make exact, fail-closed edits to the current known source
instead of replacing large collector files by hand.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRAPER = ROOT / "scripts" / "scrape_jobs.py"
COVERAGE = ROOT / "scripts" / "complete_support_coverage.py"
REGRESSION = ROOT / ".github" / "workflows" / "seoul-office-row-parser-regression.yml"
TEST = ROOT / "tests" / "test_seoul_support_subject_row_parser.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one target, found {count}")
    return text.replace(old, new, 1)


def patch_scraper() -> None:
    text = SCRAPER.read_text(encoding="utf-8")
    marker = '''    return vals\n\ndef scrape_seoul_office(src):\n'''
    helper = '''    return vals\n\n\nSEOUL_EMPTY_FIELD_VALUES = {"", "-", "–", "—", "·"}\n\n\ndef meaningful_seoul_value(value):\n    value = clean(value)\n    return "" if value in SEOUL_EMPTY_FIELD_VALUES else value\n\n\ndef seoul_subject_from_values(vals):\n    field1 = meaningful_seoul_value(first_of(vals, ["분야1", "분야 1"]))\n    field2 = meaningful_seoul_value(first_of(vals, ["분야2", "분야 2"]))\n    parts = [value for value in (field1, field2) if value]\n    if parts:\n        return " / ".join(parts)\n    return meaningful_seoul_value(first_of(vals, ["분야(과목)", "과목", "분야"]))\n\n\ndef seoul_title_from_values(vals, fallback=""):\n    explicit = meaningful_seoul_value(first_of(vals, ["제목", "공고명"]))\n    if explicit:\n        return explicit\n    subject = seoul_subject_from_values(vals)\n    if subject:\n        return subject\n    return meaningful_seoul_value(fallback)\n\n\ndef scrape_seoul_office(src):\n'''
    text = replace_once(text, marker, helper, "scraper semantic helper insertion")

    old = '''                vals=seoul_row_values(table,tr)\n                detail_anchor=seoul_detail_anchor_for_seq(tr,seq)\n                anchors=[a for a in tr.find_all("a") if clean(a.get_text(" ",strip=True))]\n                title=clean(detail_anchor.get_text(" ",strip=True) if detail_anchor else "")\n                if not title:\n                    title=first_of(vals,["제목","공고명"])\n                if not title:\n                    title=clean(max((a.get_text(" ",strip=True) for a in anchors),key=len,default=""))\n                if len(title)<3 or EXCLUDE_WORDS.search(title): continue\n                registered=date_norm(first_of(vals,["등록일","작성일"]))\n'''
    new = '''                vals=seoul_row_values(table,tr)\n                detail_anchor=seoul_detail_anchor_for_seq(tr,seq)\n                anchors=[a for a in tr.find_all("a") if clean(a.get_text(" ",strip=True))]\n                anchor_fallback=clean(detail_anchor.get_text(" ",strip=True) if detail_anchor else "")\n                if not meaningful_seoul_value(anchor_fallback):\n                    anchor_fallback=clean(max((a.get_text(" ",strip=True) for a in anchors),key=len,default=""))\n                title=seoul_title_from_values(vals,anchor_fallback)\n                subject=seoul_subject_from_values(vals)\n                if not title:\n                    parse_incomplete += 1\n                    continue\n                if EXCLUDE_WORDS.search(title): continue\n                registered=date_norm(first_of(vals,["등록일","작성일"]))\n'''
    text = replace_once(text, old, new, "scraper title selection")

    old = '''                school=first_of(vals,["학교명","기관명","작성자"]) or school_from_title(title)\n                title_school_collision = bool(school and norm(title) == norm(school)) or norm(title) == norm(office)\n                if not registered or not detail_anchor or title_school_collision:\n                    parse_incomplete += 1\n                    continue\n                raw_level=first_of(vals,["학교급별","학교급","대상"]); raw_type=first_of(vals,["직종","고용형태","구분"])\n                subject_parts=[first_of(vals,["분야1"]),first_of(vals,["분야2"])]\n                subject=" / ".join(x for x in subject_parts if x) or first_of(vals,["분야(과목)","분야","과목"])\n'''
    new = '''                school=first_of(vals,["학교명","기관명","작성자"]) or school_from_title(title)\n                title_school_collision = bool(school and norm(title) == norm(school)) or norm(title) == norm(office)\n                if not registered or title_school_collision:\n                    parse_incomplete += 1\n                    continue\n                raw_level=first_of(vals,["학교급별","학교급","대상"]); raw_type=first_of(vals,["직종","고용형태","구분"])\n'''
    text = replace_once(text, old, new, "scraper completeness gate")

    text = text.replace('"type":guess_type(raw_type+" "+title),', '"type":guess_type(raw_type+" "+title+" "+subject),', 1)
    compile(text, str(SCRAPER), "exec")
    SCRAPER.write_text(text, encoding="utf-8")


def patch_coverage() -> None:
    text = COVERAGE.read_text(encoding="utf-8")
    marker = '''    return row_vals(tr, labels)\n\n\ndef seoul_items(soup, board, detail_registration):\n'''
    helper = '''    return row_vals(tr, labels)\n\n\nSEOUL_EMPTY_FIELD_VALUES = {"", "-", "–", "—", "·"}\n\n\ndef meaningful_seoul_value(value):\n    value = clean(value)\n    return "" if value in SEOUL_EMPTY_FIELD_VALUES else value\n\n\ndef seoul_subject_from_values(vals):\n    field1 = meaningful_seoul_value(first_of(vals, ["분야1", "분야 1"]))\n    field2 = meaningful_seoul_value(first_of(vals, ["분야2", "분야 2"]))\n    parts = [value for value in (field1, field2) if value]\n    if parts:\n        return " / ".join(parts)\n    return meaningful_seoul_value(first_of(vals, ["분야(과목)", "과목", "분야"]))\n\n\ndef seoul_title_from_values(vals, fallback=""):\n    explicit = meaningful_seoul_value(first_of(vals, ["제목", "공고명"]))\n    if explicit:\n        return explicit\n    subject = seoul_subject_from_values(vals)\n    if subject:\n        return subject\n    return meaningful_seoul_value(fallback)\n\n\ndef seoul_items(soup, board, detail_registration):\n'''
    text = replace_once(text, marker, helper, "coverage semantic helper insertion")

    old = '''            vals = seoul_values(table, tr)\n            title = seoul_detail_title(tr, seq) or first_of(vals, ["제목", "공고명"])\n            school = first_of(vals, ["학교명", "기관명", "작성자"])\n'''
    new = '''            vals = seoul_values(table, tr)\n            title = seoul_title_from_values(vals, seoul_detail_title(tr, seq))\n            school = first_of(vals, ["학교명", "기관명", "작성자"])\n'''
    text = replace_once(text, old, new, "coverage title selection")

    text = replace_once(
        text,
        '''            if not title or not registered or title_school_collision:\n''',
        '''            if not title or not registered or title_school_collision:\n''',
        "coverage parse gate anchor",
    )
    text = text.replace('            if len(title) < 3 or EXCLUDE_WORDS.search(title):\n                continue\n', '            if EXCLUDE_WORDS.search(title):\n                continue\n', 1)
    text = text.replace(
        '                "subject": " / ".join(x for x in (first_of(vals,["분야1"]), first_of(vals,["분야2"])) if x),',
        '                "subject": seoul_subject_from_values(vals),',
        1,
    )
    compile(text, str(COVERAGE), "exec")
    COVERAGE.write_text(text, encoding="utf-8")


def patch_regression_workflow() -> None:
    text = REGRESSION.read_text(encoding="utf-8")
    text = text.replace("      - 'scripts/harden_seoul_office_row_parser.py'\n", "")
    text = text.replace(
        "      - 'tests/test_seoul_support_exact_detail_metadata.py'\n",
        "      - 'tests/test_seoul_support_exact_detail_metadata.py'\n      - 'tests/test_seoul_support_subject_row_parser.py'\n",
    )
    text = text.replace("permissions:\n  contents: write\n", "permissions:\n  contents: read\n")
    text = text.replace(
        "      - name: Apply idempotent Seoul parser hardening\n        run: python scripts/harden_seoul_office_row_parser.py\n",
        "",
    )
    text = text.replace(
        "      - name: Compile scraper and independent coverage parser\n        run: python -m py_compile scripts/scrape_jobs.py scripts/complete_support_coverage.py scripts/seoul_support_detail_metadata.py scripts/harden_seoul_office_row_parser.py\n",
        "      - name: Compile scraper and independent coverage parser\n        run: python -m py_compile scripts/scrape_jobs.py scripts/complete_support_coverage.py scripts/seoul_support_detail_metadata.py\n",
    )
    exact_step = "      - name: Exact official-detail metadata regression\n        run: python -m unittest discover -s tests -p test_seoul_support_exact_detail_metadata.py\n"
    text = text.replace(
        exact_step,
        exact_step + "      - name: Multi-anchor subject-row regression\n        run: python -m unittest discover -s tests -p test_seoul_support_subject_row_parser.py\n",
    )
    start = text.find("      - name: Fail if generated hardening is not idempotent\n")
    if start == -1:
        raise SystemExit("regression hardener cleanup: start not found")
    text = text[:start].rstrip() + "\n"
    REGRESSION.write_text(text, encoding="utf-8")


def write_test() -> None:
    TEST.write_text(r'''import sys
import unittest
from bs4 import BeautifulSoup

sys.path.insert(0, "scripts")
import scrape_jobs as scraper
import complete_support_coverage as coverage


class SeoulSupportSubjectRowParserTests(unittest.TestCase):
    def row(self, field1, field2="-"):
        html = f"""
        <table>
          <thead><tr>
            <th>구분</th><th>학교명</th><th>분야1</th><th>분야2</th><th>등록일</th><th>마감일</th>
          </tr></thead>
          <tbody><tr>
            <td><a href='#' onclick="fncDetailView('15140');">기간제</a></td>
            <td>서울신은초등학교병설유치원</td>
            <td><a href='#' onclick="fncDetailView('15140');">{field1}</a></td>
            <td><a href='#' onclick="fncDetailView('15140');">{field2}</a></td>
            <td>2026.10.01</td><td>-</td>
          </tr></tbody>
        </table>
        """
        soup = BeautifulSoup(html, "html.parser")
        return soup, soup.table, soup.table.tbody.tr

    def test_placeholder_final_anchor_does_not_hide_field1(self):
        soup, table, tr = self.row("가을 단기방학 에듀케어 대체강사", "-")
        vals = scraper.seoul_row_values(table, tr)
        anchor = scraper.seoul_detail_anchor_for_seq(tr, "15140")
        self.assertEqual(scraper.clean(anchor.get_text(" ", strip=True)), "-")
        self.assertEqual(
            scraper.seoul_title_from_values(vals, anchor.get_text(" ", strip=True)),
            "가을 단기방학 에듀케어 대체강사",
        )
        self.assertEqual(scraper.seoul_subject_from_values(vals), "가을 단기방학 에듀케어 대체강사")

        items, dates, expected, candidates, incomplete = coverage.seoul_items(soup, "https://example.sen.go.kr/FUS/JO/JOL11.do", {})
        self.assertTrue(expected)
        self.assertEqual(candidates, 1)
        self.assertEqual(incomplete, 0)
        self.assertEqual(items[0][0], "15140")
        self.assertEqual(items[0][1], "가을 단기방학 에듀케어 대체강사")
        self.assertEqual(dates, ["2026/10/01"])

    def test_two_character_subject_is_valid(self):
        soup, table, tr = self.row("영어", "-")
        vals = scraper.seoul_row_values(table, tr)
        self.assertEqual(scraper.seoul_title_from_values(vals, "-"), "영어")
        self.assertEqual(scraper.seoul_subject_from_values(vals), "영어")
        items, _, _, _, incomplete = coverage.seoul_items(soup, "https://example.sen.go.kr/FUS/JO/JOL11.do", {})
        self.assertEqual(incomplete, 0)
        self.assertEqual(items[0][1], "영어")

    def test_second_real_subject_is_preserved(self):
        _, table, tr = self.row("6학년 영어", "기간제")
        vals = scraper.seoul_row_values(table, tr)
        self.assertEqual(scraper.seoul_title_from_values(vals, "기간제"), "6학년 영어 / 기간제")
        self.assertEqual(scraper.seoul_subject_from_values(vals), "6학년 영어 / 기간제")


if __name__ == "__main__":
    unittest.main()
''', encoding="utf-8")


def main() -> None:
    patch_scraper()
    patch_coverage()
    patch_regression_workflow()
    write_test()
    print("P0 Seoul support subject-row parser patch prepared")


if __name__ == "__main__":
    main()
