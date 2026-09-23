import unittest

from scripts.verify_published_scan_completeness import VerificationError, verify


def job(sid):
    prefix, value = sid.split(":", 1)
    if prefix == "goe-central":
        return {
            "province": "경기",
            "sourceType": "통합게시판",
            "url": f"https://www.goe.go.kr/recruit/view.do?pbancSn={value}",
        }
    if prefix == "ice-central":
        return {
            "province": "인천",
            "bbsId": "1981",
            "nttSn": value,
            "url": f"https://www.ice.go.kr/ice/na/ntt/selectNttInfo.do?bbsId=1981&mi=10997&nttSn={value}",
        }
    raise AssertionError(sid)


def ledger(ids, generated="2026-09-23 12:00:00 KST"):
    return {
        "generatedAt": generated,
        "populationPolicy": "p",
        "officialIdCount": len(ids),
        "entries": {
            sid: {"presentInLatestOfficialScan": True}
            for sid in ids
        },
    }


def report(ids, missing_before=0, generated="2026-09-23 12:00:00 KST", expected=2):
    return {
        "generatedAt": generated,
        "populationPolicy": "p",
        "summary": {
            "populationPolicy": "p",
            "officialIdCount": len(ids),
            "missingBefore": missing_before,
            "missingAfter": 0,
            "reconciledSources": expected,
            "totalSources": expected,
        },
        "incompleteSources": [],
    }


class PublishedScanCompletenessTests(unittest.TestCase):
    def test_live_only_delta_does_not_retroactively_fail_snapshot(self):
        published_ids = {"goe-central:1", "ice-central:10"}
        live_ids = published_ids | {"goe-central:2"}
        published_jobs = {
            "jobs": [job(x) for x in sorted(published_ids)] * 50,
            "sourceReconciliation": {
                "officialIdCount": 2,
                "missingAfter": 0,
                "reconciledSources": 2,
                "totalSources": 2,
            },
        }
        result = verify(
            published_jobs,
            ledger(published_ids),
            report(published_ids),
            ledger(live_ids, generated="2026-09-23 13:00:00 KST"),
            report(live_ids, missing_before=1, generated="2026-09-23 13:00:00 KST"),
            expected_sources=2,
        )
        self.assertEqual(result["publishedScan"]["missingFromPublishedJobs"], 0)
        self.assertEqual(result["liveAudit"]["idsAbsentFromPublishedJobs"], 1)

    def test_id_present_in_published_ledger_but_missing_from_jobs_fails(self):
        published_ids = {"goe-central:1", "ice-central:10"}
        published_jobs = {
            "jobs": [job("goe-central:1")] * 100,
            "sourceReconciliation": {
                "officialIdCount": 2,
                "missingAfter": 0,
                "reconciledSources": 2,
                "totalSources": 2,
            },
        }
        with self.assertRaisesRegex(VerificationError, "already present"):
            verify(
                published_jobs,
                ledger(published_ids),
                report(published_ids),
                ledger(published_ids, generated="2026-09-23 13:00:00 KST"),
                report(published_ids, missing_before=1, generated="2026-09-23 13:00:00 KST"),
                expected_sources=2,
            )

    def test_live_missing_after_still_fails_closed(self):
        published_ids = {"goe-central:1"}
        live = report(published_ids, expected=1)
        live["summary"]["missingAfter"] = 1
        published_jobs = {
            "jobs": [job("goe-central:1")] * 100,
            "sourceReconciliation": {
                "officialIdCount": 1,
                "missingAfter": 0,
                "reconciledSources": 1,
                "totalSources": 1,
            },
        }
        with self.assertRaisesRegex(VerificationError, "missingAfter"):
            verify(
                published_jobs,
                ledger(published_ids),
                report(published_ids, expected=1),
                ledger(published_ids),
                live,
                expected_sources=1,
            )

    def test_published_report_and_ledger_must_share_scan_window(self):
        ids = {"goe-central:1"}
        published_jobs = {
            "jobs": [job("goe-central:1")] * 100,
            "sourceReconciliation": {
                "officialIdCount": 1,
                "missingAfter": 0,
                "reconciledSources": 1,
                "totalSources": 1,
            },
        }
        with self.assertRaisesRegex(VerificationError, "same scan window"):
            verify(
                published_jobs,
                ledger(ids, generated="2026-09-23 11:59:00 KST"),
                report(ids, expected=1, generated="2026-09-23 12:00:00 KST"),
                ledger(ids, generated="2026-09-23 13:00:00 KST"),
                report(ids, expected=1, generated="2026-09-23 13:00:00 KST"),
                expected_sources=1,
            )


if __name__ == "__main__":
    unittest.main()
