import unittest
from datetime import datetime, timedelta, timezone

from scripts.measure_visibility_latency import build_report, parse_time, percentile


class VisibilityLatencyTests(unittest.TestCase):
    def test_parse_kst(self):
        self.assertEqual(
            parse_time("2026-09-27 00:23:35 KST").isoformat(),
            "2026-09-26T15:23:35+00:00",
        )

    def test_percentile_nearest_rank(self):
        self.assertEqual(percentile([1, 2, 3, 4], 0.95), 4.0)

    def test_report_flags_sparse_fast_cadence(self):
        runs = []
        fast_times = [
            "2026-09-25T18:00:00Z",
            "2026-09-26T00:00:00Z",
            "2026-09-26T06:00:00Z",
            "2026-09-26T12:00:00Z",
        ]
        for i, ts in enumerate(fast_times, 1):
            runs.append({
                "id": i,
                "name": "Update 수도권 education jobs",
                "conclusion": "success",
                "created_at": ts,
                "run_started_at": ts,
                "updated_at": ts,
            })
        runs.extend([
            {
                "id": 100,
                "name": "Unified recruitment search",
                "conclusion": "success",
                "created_at": "2026-09-26T12:05:00Z",
                "run_started_at": "2026-09-26T12:05:00Z",
                "updated_at": "2026-09-26T12:10:00Z",
            },
            {
                "id": 101,
                "name": "pages build and deployment",
                "conclusion": "success",
                "created_at": "2026-09-26T12:10:05Z",
                "run_started_at": "2026-09-26T12:10:05Z",
                "updated_at": "2026-09-26T12:11:00Z",
            },
        ])
        ledger = {
            "entries": {
                "gg:test:1": {
                    "province": "경기",
                    "source": "테스트",
                    "registered": "2026/09/26",
                    "firstSeen": "2026-09-26 20:59:00 KST",
                }
            }
        }
        report = build_report(
            ledger=ledger,
            runs=runs,
            now=datetime(2026, 9, 26, 13, 0, tzinfo=timezone.utc),
            window_hours=24,
            slo_hours=4,
        )
        self.assertEqual(
            report["fourHourVisibilitySloProxy"]["status"],
            "fail",
        )
        self.assertEqual(
            report["detectedToVisible"]["matchedSamples"],
            1,
        )

    def test_missing_unified_after_slo_is_censored_violation(self):
        now = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)
        ledger = {
            "entries": {
                "gg:test:censored": {
                    "province": "경기",
                    "source": "테스트",
                    "registered": "2026/09/29",
                    "firstSeen": (now - timedelta(hours=5)).isoformat(),
                }
            }
        }
        report = build_report(
            ledger=ledger,
            runs=[],
            now=now,
            window_hours=24,
            slo_hours=4,
        )
        detected = report["detectedToVisible"]
        self.assertEqual(detected["matchedSamples"], 0)
        self.assertEqual(detected["pendingSamples"], 0)
        self.assertEqual(detected["censoredViolations"], 1)
        self.assertEqual(detected["sloCompliance"]["complianceRate"], 0.0)
        self.assertTrue(detected["censoredP95"]["p95IsLowerBound"])
        self.assertGreaterEqual(
            detected["censoredP95"]["p95LowerBoundMinutes"],
            300,
        )

    def test_missing_unified_within_slo_is_pending_not_violation(self):
        now = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)
        ledger = {
            "entries": {
                "gg:test:pending": {
                    "province": "경기",
                    "source": "테스트",
                    "registered": "2026/09/29",
                    "firstSeen": (now - timedelta(hours=2)).isoformat(),
                }
            }
        }
        report = build_report(
            ledger=ledger,
            runs=[],
            now=now,
            window_hours=24,
            slo_hours=4,
        )
        detected = report["detectedToVisible"]
        self.assertEqual(detected["matchedSamples"], 0)
        self.assertEqual(detected["pendingSamples"], 1)
        self.assertEqual(detected["censoredViolations"], 0)
        self.assertIsNone(detected["sloCompliance"]["complianceRate"])

    def test_missing_pages_after_slo_is_not_dropped(self):
        now = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)
        seen = now - timedelta(hours=5)
        runs = [
            {
                "id": 100,
                "name": "Unified recruitment search",
                "conclusion": "success",
                "created_at": (seen + timedelta(minutes=10)).isoformat(),
                "run_started_at": (seen + timedelta(minutes=10)).isoformat(),
                "updated_at": (seen + timedelta(minutes=15)).isoformat(),
            }
        ]
        ledger = {
            "entries": {
                "gg:test:no-pages": {
                    "province": "서울",
                    "source": "테스트",
                    "registered": "2026/09/29",
                    "firstSeen": seen.isoformat(),
                }
            }
        }
        report = build_report(
            ledger=ledger,
            runs=runs,
            now=now,
            window_hours=24,
            slo_hours=4,
        )
        sample = report["detectedToVisible"]["sample"][0]
        self.assertEqual(sample["status"], "censored_violation")
        self.assertEqual(sample["violationStage"], "pages")
        self.assertEqual(report["detectedToVisible"]["censoredViolations"], 1)

    def test_matched_sample_over_slo_counts_as_violation(self):
        now = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)
        seen = now - timedelta(hours=6)
        runs = [
            {
                "id": 100,
                "name": "Unified recruitment search",
                "conclusion": "success",
                "created_at": (seen + timedelta(hours=4)).isoformat(),
                "run_started_at": (seen + timedelta(hours=4)).isoformat(),
                "updated_at": (seen + timedelta(hours=4, minutes=10)).isoformat(),
            },
            {
                "id": 101,
                "name": "pages build and deployment",
                "conclusion": "success",
                "created_at": (seen + timedelta(hours=4, minutes=20)).isoformat(),
                "run_started_at": (seen + timedelta(hours=4, minutes=20)).isoformat(),
                "updated_at": (seen + timedelta(hours=4, minutes=30)).isoformat(),
            },
        ]
        ledger = {
            "entries": {
                "gg:test:late": {
                    "province": "인천",
                    "source": "테스트",
                    "registered": "2026/09/29",
                    "firstSeen": seen.isoformat(),
                }
            }
        }
        report = build_report(
            ledger=ledger,
            runs=runs,
            now=now,
            window_hours=24,
            slo_hours=4,
        )
        detected = report["detectedToVisible"]
        self.assertEqual(detected["matchedSamples"], 1)
        self.assertEqual(detected["sloCompliance"]["matchedViolations"], 1)
        self.assertEqual(detected["sloCompliance"]["complianceRate"], 0.0)

    def test_rerun_attempt_is_not_misclassified_as_queue_delay(self):
        runs = [
            {
                "id": 1,
                "name": "Production operations watchdog",
                "event": "schedule",
                "run_attempt": 2,
                "conclusion": "success",
                "created_at": "2026-09-26T00:00:00Z",
                "run_started_at": "2026-09-26T04:00:00Z",
                "updated_at": "2026-09-26T04:01:00Z",
            }
        ]
        report = build_report(
            ledger={"entries": {}},
            runs=runs,
            now=datetime(2026, 9, 26, 5, 0, tzinfo=timezone.utc),
            window_hours=24,
            slo_hours=4,
        )
        watchdog = report["workflowStats"]["Production operations watchdog"]
        self.assertEqual(watchdog["rerunAttempts"], 1)
        self.assertEqual(watchdog["queueMinutes"]["count"], 0)

    def test_report_does_not_invent_official_timestamp(self):
        report = build_report(
            ledger={"entries": {}},
            runs=[],
            now=datetime(2026, 9, 26, 13, 0, tzinfo=timezone.utc),
            window_hours=48,
            slo_hours=4,
        )
        self.assertEqual(report["fourHourVisibilitySloProxy"]["status"], "insufficient-data")
        self.assertIn("date-only", report["measurementLimits"]["officialRegistrationTimestamp"])


if __name__ == "__main__":
    unittest.main()
