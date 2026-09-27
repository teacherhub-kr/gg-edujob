import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import repair_seoul_support_metadata as repair


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
        html = """<table><tr><th>등록일자</th><td>2026-09-03</td><th>마감일자</th><td>2026-10-03</td></tr>
        <tr><th>기관명</th><td>서울어울초등학교</td></tr>
        <tr><th>직종</th><td>전체</td><th>분야(과목)</th><td>초등예술하나 연극 강사(6학년)</td></tr></table>"""
        self.assertEqual(repair.repair(job, Session(html)), "repaired")
        self.assertEqual(job["title"], "초등예술하나 연극 강사(6학년)")
        self.assertEqual(job["registered"], "2026/09/03")

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


if __name__ == "__main__":
    unittest.main()
