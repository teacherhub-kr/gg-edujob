#!/usr/bin/env python3
"""Fail-closed regressions for verified delisted Gyeonggi source detail URLs."""
import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import quarantine_verified_delisted_support as q

BOARD="https://www.gpoe.kr/gpoe/na/ntt/selectNttList.do?bbsId=5218&mi=9406"
REGISTRY={"gyeonggi":{"supportOffices":[
    {"name":"김포교육지원청","boardUrls":[BOARD],"regions":["김포시"]}]}}
def row(native,school="김포금빛초"):
    return {"province":"경기","source":"김포교육지원청",
            "sourceType":"교육지원청 개별 게시판",
            "school":school,"title":"시간강사 채용 공고","registered":"2026/11/19",
            "url":f"https://www.gpoe.kr/gpoe/na/ntt/selectNttInfo.do?bbsId=5218&mi=9406&nttSn={native}"}
def failed(native=1148220,status=400):
    return {"url":row(native)["url"],"status":status,"hard":True}
def proof(**overrides):
    return {**{"coverageComplete":True,"crossedLookback":True,
            "accessError":False,"paginationRepeated":False,
            "paginationCounterMismatch":False},**overrides}


class VerifiedDelistedLinkTests(unittest.TestCase):
    def test_official_90day_absence_and_repeat_400_quarantines_one(self):
        original=[row(1148220),row(1148251)]
        s=Mock(return_value=([row(1148251)],proof()))
        p=Mock(return_value=True)
        remaining,report=q.quarantine(original,[failed()],REGISTRY,s,p)
        self.assertEqual([q.canonical_board_id(x["url"],BOARD) for x in remaining],["1148251"])
        self.assertEqual(report["quarantined"],1)
        self.assertEqual(report["ids"],["1148220"])
        s.assert_called_once()
        p.assert_called_once()
        self.assertEqual(len(original),2)  # no in-place mutation

    def test_still_listed_official_id_cannot_be_quarantined(self):
        original=[row(1148220)]
        p=Mock(return_value=True)
        result,report=q.quarantine(original,[failed()],REGISTRY,lambda *a:([row(1148220)],proof()),p)
        self.assertEqual(report["quarantined"],0)
        self.assertEqual(result,original)
        p.assert_not_called()

    def test_incomplete_90day_board_fails_closed(self):
        original=[row(1148220)]
        for health in ({"coverageComplete":False},
                       {"paginationRepeated":True},
                       {"accessError":True},
                       {"paginationCounterMismatch":True}):
            with self.subTest(health=health),self.assertRaisesRegex(ValueError,"proof incomplete"):
                q.quarantine(original,[failed()],REGISTRY,
                             lambda *a:([row(1148251)],proof(**health)),lambda *a:True)
        self.assertEqual(len(original),1)

    def test_detail_not_confirmed_deleted_remains_fail_closed_for_next_validator(self):
        original=[row(1148220)]
        result,report=q.quarantine(original,[failed()],REGISTRY,
            lambda *a:([row(1148251)],proof()),lambda *a:False)
        self.assertEqual(result,original)
        self.assertEqual(report["quarantined"],0)

    def test_403_or_500_is_not_eligible_for_auto_quarantine(self):
        original=[row(1148220)]
        scan=Mock(side_effect=AssertionError("no scan"))
        for status in (403,429,500,"Timeout"):
            result,report=q.quarantine(original,[failed(status=status)],REGISTRY,scan,lambda *a:True)
            self.assertEqual(result,original)
            self.assertEqual(report["checkedDeadLinks"],0)
        scan.assert_not_called()

    def test_fake_host_or_wrong_board_cannot_be_quarantined(self):
        wrong=row(1148220)
        wrong["url"]=wrong["url"].replace("www.gpoe.kr","attacker.invalid")
        self.assertEqual(q.canonical_board_id(wrong["url"],BOARD),"")
        wrongboard=row(1148220)
        wrongboard["url"]=wrongboard["url"].replace("bbsId=5218","bbsId=8411")
        self.assertEqual(q.canonical_board_id(wrongboard["url"],BOARD),"")
        for j in (wrong,wrongboard):
            scan=Mock(side_effect=AssertionError("no unsafe source scan"))
            result,report=q.quarantine([j],[{"url":j["url"],"hard":True,"status":400}],
                                       REGISTRY,scan,lambda *a:True)
            self.assertEqual(len(result),1)
            scan.assert_not_called()

    def test_same_title_other_source_native_id_preserved(self):
        original=[row(1148220),row(1148251)]
        result,_=q.quarantine(original,[failed()],REGISTRY,
                            lambda *a:([row(1148251)],proof()),lambda *a:True)
        self.assertEqual(result[0]["url"],original[1]["url"])


class ProactiveKimpoSourceCoverageTests(unittest.TestCase):
    def test_delisted_link_quarantined_even_if_not_selected_by_50_link_sample(self):
        original=[row(1148220),row(1148251)]
        scan=Mock(return_value=([row(1148251)],proof()))
        probe=Mock(return_value=True)
        result,report=q.proactively_quarantine_office(original,REGISTRY,"김포교육지원청",scan,probe)
        self.assertEqual(len(result),1)
        self.assertEqual(q.canonical_board_id(result[0]["url"],BOARD),"1148251")
        self.assertEqual(report["ids"],["1148220"])
        self.assertTrue(report["sourceScanned"])
        scan.assert_called_once()
        probe.assert_called_once()

    def test_all_listed_ids_are_retained_no_probe(self):
        original=[row(1148220),row(1148251)]
        probe=Mock(side_effect=AssertionError("should not request active detail"))
        result,report=q.proactively_quarantine_office(
            original,REGISTRY,"김포교육지원청",
            lambda *a:(list(original),proof()),probe)
        self.assertEqual(result,original)
        self.assertEqual(report["quarantined"],0)
        probe.assert_not_called()

    def test_failed_independent_source_proof_cannot_authorize_any_deletion(self):
        original=[row(1148220)]
        with self.assertRaisesRegex(ValueError,"proof incomplete"):
            q.proactively_quarantine_office(
                original,REGISTRY,"김포교육지원청",
                lambda *a:([row(1148251)],proof(paginationRepeated=True)),lambda *a:True)
        self.assertEqual(len(original),1)

    def test_many_missing_ids_fail_closed_instead_of_mass_deleting(self):
        original=[row(1148220+i) for i in range(q.MAX_SUSPECTS+1)]
        with self.assertRaisesRegex(ValueError,"refuse bulk quarantine"):
            q.proactively_quarantine_office(
                original,REGISTRY,"김포교육지원청",
                lambda *a:([row(1150000)],proof()),lambda *a:True)

    def test_dead_link_not_reconfirmed_remains_published_candidate(self):
        original=[row(1148220)]
        result,report=q.proactively_quarantine_office(
            original,REGISTRY,"김포교육지원청",
            lambda *a:([row(1148251)],proof()),lambda *a:False)
        self.assertEqual(result,original)
        self.assertEqual(report["quarantined"],0)


if __name__=="__main__":
    unittest.main()
