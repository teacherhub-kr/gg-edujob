#!/usr/bin/env python3
"""P0: live-listed source IDs must not disappear from published Regional jobs."""
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import reconcile_seoul_central_ids as recon


def row(sid, registered="2026/11/05"):
    return {
        "id": "sen-" + str(sid),
        "province": "서울",
        "sourceType": "통합게시판",
        "source": "서울교육일자리포털",
        "school": "서울북한산유치원",
        "title": "(서울북한산유) 2026학년도 겨울방학 방과후 과정 대체강사 채용 공고",
        "registered": registered,
        "applyEnd": "2026/12/04",
        "url": "https://work.sen.go.kr/work/search/recInfo/BD_selectRecDetail.do?q_rcrtSn=" + str(sid),
    }


def proof(ids):
    return {
        "complete": True,
        "sources": [{
            "province": "서울", "name": "서울교육일자리포털",
            "complete": True, "stableIdCount": len(ids),
            "sourceNativeRecruitmentIds": [str(x) for x in ids],
            "parseError": False, "accessError": False,
            "paginationRepeated": False, "capHit": False,
        }],
    }


def candidate(rows):
    return {
        "jobs": rows,
        "sources": {"seoul": {"central": {"name": "서울교육일자리포털", "ok": True,
                                          "count": len(rows)}}},
    }


class SeoulCentralNativeReconciliationTests(unittest.TestCase):
    def test_active_source_113663_recovered_only_from_verified_live_collector(self):
        source = [row(114467, registered="2026/11/13")]
        fetch = Mock(return_value=[row(113663), row(114467, registered="2026/11/13")])
        result = recon.reconcile(candidate(source), proof([113663, 114467]), fetch)
        fetch.assert_called_once_with()
        self.assertEqual({recon.native_id(j) for j in result["jobs"]}, {"113663", "114467"})
        self.assertEqual(result["seoulCentralIdReconciliation"]["previousMissing"], 1)
        self.assertEqual(result["seoulCentralIdReconciliation"]["recoveredNow"], 1)
        self.assertEqual(result["seoulCentralIdReconciliation"]["missingAfter"], 0)
        self.assertEqual(result["sources"]["seoul"]["central"]["count"], 2)
        self.assertEqual(len(source), 1)  # no in-place mutation of candidate input

    def test_no_recovery_crawl_when_source_id_set_already_complete(self):
        fetch = Mock(side_effect=AssertionError("no additional live request permitted"))
        result = recon.reconcile(candidate([row(113663)]), proof([113663]), fetch)
        fetch.assert_not_called()
        self.assertEqual(result["seoulCentralIdReconciliation"]["recoveredNow"], 0)

    def test_same_school_title_and_date_but_distinct_official_ids_both_retained(self):
        duplicate = row(113664)
        duplicate["registered"] = "2026/11/05"
        result = recon.reconcile(candidate([row(113663)]), proof([113663, 113664]),
                                 lambda: [row(113663), duplicate])
        self.assertEqual(len(result["jobs"]), 2)
        self.assertNotEqual(recon.native_id(result["jobs"][0]), recon.native_id(result["jobs"][1]))

    def test_unrecovered_native_id_fails_closed_and_does_not_mutate(self):
        base = candidate([row(114467)])
        fetch = Mock(return_value=[row(114467)])
        with self.assertRaisesRegex(ValueError, "unrecovered"):
            recon.reconcile(base, proof([113663, 114467]), fetch)
        self.assertEqual(len(base["jobs"]), 1)
        self.assertNotIn("seoulCentralIdReconciliation", base)

    def test_nonfirstparty_or_wrong_province_cannot_restore_id(self):
        bad = row(113663)
        bad["url"] = "https://untrusted.example/work/search/recInfo/BD_selectRecDetail.do?q_rcrtSn=113663"
        self.assertEqual(recon.native_id(bad), "")
        with self.assertRaisesRegex(ValueError, "unrecovered"):
            recon.reconcile(candidate([]), proof([113663]), lambda: [bad])

    def test_independent_proof_replay_fail_closed(self):
        stale = proof([113663])
        stale["sources"][0]["paginationRepeated"] = True
        with self.assertRaisesRegex(ValueError, "not trustworthy"):
            recon.reconcile(candidate([]), stale, lambda: [row(113663)])

    def test_count_only_audit_is_rejected(self):
        missing_ids = proof([113663])
        del missing_ids["sources"][0]["sourceNativeRecruitmentIds"]
        with self.assertRaisesRegex(ValueError, "no count-only pass"):
            recon.reconcile(candidate([]), missing_ids, lambda: [row(113663)])


if __name__ == "__main__":
    unittest.main()
