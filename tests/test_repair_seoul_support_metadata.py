import sys
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import repair_seoul_support_metadata as repair
import complete_support_coverage as coverage
from bs4 import BeautifulSoup


class Response:
    encoding = "utf-8"
    apparent_encoding = "utf-8"

    def __init__(self, html):
        self.text = html

    def raise_for_status(self):
        pass


class Session:
    def __init__(self, html):
        self.html = html

    def post(self, *args, **kwargs):
        return Response(self.html)

    def get(self, *args, **kwargs):
        return Response(self.html)


class TestExactSeoulDetailRepair(unittest.TestCase):
    def job(self):
        return {
            "province": "서울", "sourceType": "교육지원청 개별 게시판", "openMethod": "POST",
            "openUrl": "https://sbedu.sen.go.kr/FUS/JO/JOV11.do",
            "boardUrl": "https://sbedu.sen.go.kr/FUS/JO/JOL11.do",
            "openParams": {"job_seq": "5592"}, "school": "서울어울초등학교",
            "source": "서울특별시서부교육지원청", "title": "서울어울초등학교",
            "applyEnd": "2026/10/03", "registered": "",
        }

    def test_recovers_labelled_fields_only(self):
        job = self.job()
        job.update({"id": "sen-complete-sbedu.sen.go.kr-5592", "registered": "2026/09/03",
                    "applyStart": "2026/09/03", "periodStatus": "unavailable"})
        html = """<table><tr><th>등록일자</th><td>2026-09-03</td><th>마감일자</th><td>2026-10-03</td></tr>
        <tr><th>기관명</th><td>서울어울초등학교</td></tr>
        <tr><th>직종</th><td>전체</td><th>분야(과목)</th><td>초등예술하나 연극 강사(6학년)</td></tr></table>"""
        self.assertEqual(repair.repair(job, Session(html)), "repaired")
        self.assertEqual(job["title"], "초등예술하나 연극 강사(6학년)")
        self.assertEqual(job["registered"], "2026/09/03")
        self.assertEqual(job["applyStart"], "")
        self.assertEqual(repair.exact_registration_from_detail(
            Session(html), job["boardUrl"], "5592", job["school"], job["applyEnd"]), "2026/09/03")
        self.assertEqual(repair.exact_registration_from_detail(
            Session(html), job["boardUrl"], "5592", "다른학교", job["applyEnd"]), "")

    def test_empty_or_conflicting_detail_preserves_job(self):
        job = self.job()
        before = dict(job)
        self.assertEqual(repair.repair(job, Session("<table><tr><th>등록일자</th><td></td></tr></table>")), "detail-empty-or-incomplete")
        self.assertEqual(job, before)
        html = """<tr><th>등록일자</th><td>2026-09-03</td><th>마감일자</th><td>2026-10-04</td></tr>
        <tr><th>기관명</th><td>서울어울초등학교</td></tr>
        <tr><th>분야(과목)</th><td>연극 강사</td></tr>"""
        self.assertEqual(repair.repair(job, Session(html)), "detail-deadline-conflict")
        self.assertEqual(job, before)

    def test_absence_requires_complete_matching_board_lists(self):
        board = "https://sbedu.sen.go.kr/FUS/JO/JOL11.do"
        html = """<div>Total : 1 개 (Page 1/1)</div>
        <a href="javascript:fncDetailView('5592');">공고</a>"""
        self.assertTrue(repair.prove_absent_from_board(Session(html), board, "5596"))
        self.assertFalse(repair.prove_absent_from_board(Session(html), board, "5592"))
        incomplete = html.replace("Total : 1 개", "Total : 2 개")
        self.assertFalse(repair.prove_absent_from_board(Session(incomplete), board, "5596"))

    def test_list_without_registration_uses_matching_official_detail(self):
        board = "https://sbedu.sen.go.kr/FUS/JO/JOL11.do"
        html = """<table><tr><th>기관명</th><th>분야(과목)</th><th>마감일</th></tr><tr>
        <td><a href="javascript:fncDetailView('5592');">서울어울초등학교</a></td>
        <td><a href="javascript:fncDetailView('5592');">초등예술하나 연극 강사</a></td>
        <td>2026-10-03</td></tr></table>"""
        with patch.object(coverage, "exact_registration_from_detail", return_value="2026/09/03") as fetch:
            coverage.SEOUL_DETAIL_REGISTRATION.clear()
            rows, dates, _, _, incomplete = coverage.seoul_items(BeautifulSoup(html, "html.parser"), board)
        self.assertEqual((len(rows), dates, incomplete), (1, ["2026/09/03"], 0))
        fetch.assert_called_once_with(coverage.S, board, "5592", "서울어울초등학교", "2026-10-03")

    def test_stale_carry_removed_only_when_ledger_and_board_agree(self):
        class OfficialSession(Session):
            headers = {}

            def post(self, url, *args, **kwargs):
                if url.endswith("/JOV11.do"):
                    return Response("<tr><th>등록일자</th><td></td></tr>")
                return super().post(url, *args, **kwargs)

        board = "https://gdspedu.sen.go.kr/FUS/JO/JOL11.do"
        listing = """<div>Total : 1 개 (Page 1/1)</div>
        <a href="javascript:fncDetailView('8323');">공고</a>"""
        job = self.job()
        job.update({"id": "stale-8319", "boardUrl": board,
                    "openUrl": "https://gdspedu.sen.go.kr/FUS/JO/JOV11.do",
                    "url": "https://gdspedu.sen.go.kr/FUS/JO/JOV11.do?job_seq=8319",
                    "openParams": {"job_seq": "8319"}, "applyEnd": "2026/10/12",
                    "registered": "2026/09/12", "title": "서울어울초등학교"})
        sid = "seoul:gdspedu.sen.go.kr:8319"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            jobs_path, ledger_path, report_path = (root / x for x in ("jobs.json", "ledger.json", "report.json"))
            for protected in (False, True):
                jobs_path.write_text(json.dumps({"jobs": [job]}, ensure_ascii=False))
                ledger_path.write_text(json.dumps({"entries": {sid: {"presentInLatestOfficialScan": protected}}}))
                with patch.object(repair, "JOBS_PATH", jobs_path), patch.object(repair, "LEDGER_PATH", ledger_path), \
                     patch.object(repair, "REPORT_PATH", report_path), patch.object(repair.requests, "Session", return_value=OfficialSession(listing)):
                    repair.main()
                remaining = json.loads(jobs_path.read_text())["jobs"]
                self.assertEqual(len(remaining), 1 if protected else 0)


if __name__ == "__main__":
    unittest.main()
