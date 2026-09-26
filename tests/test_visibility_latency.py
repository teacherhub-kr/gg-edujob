import unittest
from datetime import datetime, timezone

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
