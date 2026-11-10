import copy
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import publish_seoul_gyeonggi_snapshot as sg  # noqa: E402
import validate_required_metro_publication as guard  # noqa: E402


def scenario():
    registry = json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))
    sources = {}
    for key in ("gyeonggi", "seoul"):
        offices = []
        for office in registry[key]["supportOffices"]:
            offices.append({
                "name": office["name"], "ok": True, "coverageComplete": True,
                "boardHealth": [{
                    "url": "https://example.invalid/read",
                    "pagesScanned": 1, "coverageComplete": True,
                    "accessError": False, "paginationRepeated": False,
                    "naturalEnd": True,
                }]
            })
        sources[key] = {
            "central": {"ok": True, "count": 50},
            "supportOffices": offices,
        }
    rows = [
        {"province": "경기" if i % 2 else "서울", "id": f"synthetic:{i}", "title": f"테스트 {i}"}
        for i in range(120)
    ]
    candidate = {
        "jobs": rows, "sources": sources, "errors": [],
        "regionalCentral90d": {"coverageComplete": True, "sourceRows": 100},
        "supportCompleteness": {
            "lookbackDays": 90, "gyeonggiComplete": 25, "gyeonggiTotal": 25,
            "seoulComplete": 11, "seoulTotal": 11,
        },
        "supportLinkResolution": {
            "gyeonggiTotal": 40, "gyeonggiExact": 40,
            "seoulTotal": 20, "seoulExact": 20,
        },
        "verification": {"state": "ok"},
    }
    central = {
        "complete": True,
        "sources": [
            {"province": "경기", "complete": True, "stableIdCount": 50},
            {"province": "서울", "complete": True, "stableIdCount": 50},
        ],
    }
    gyeonggi = {"complete": True, "lookbackDays": 90, "stableIdCount": 100}
    return candidate, registry, central, gyeonggi


class RegionalSnapshotTests(unittest.TestCase):
    def test_complete_two_region_proof_accepted(self):
        c, reg, central, gg = scenario()
        self.assertEqual(sg.validate_snapshot(c, reg, central, gg), {"gyeonggi": 60, "seoul": 60})

    def test_missing_office_fails_closed(self):
        c, reg, central, gg = scenario()
        c["sources"]["seoul"]["supportOffices"].pop()
        with self.assertRaisesRegex(ValueError, "registry mismatch"):
            sg.validate_snapshot(c, reg, central, gg)

    def test_truncated_board_fails_closed(self):
        c, reg, central, gg = scenario()
        c["sources"]["gyeonggi"]["supportOffices"][0]["boardHealth"][0]["paginationRepeated"] = True
        with self.assertRaisesRegex(ValueError, "unproven board traversal"):
            sg.validate_snapshot(c, reg, central, gg)

    def test_incheon_job_cannot_enter_regional_snapshot(self):
        c, reg, central, gg = scenario()
        c["jobs"].append({"province": "인천", "title": "금지"})
        with self.assertRaisesRegex(ValueError, "non-Seoul/Gyeonggi"):
            sg.validate_snapshot(c, reg, central, gg)

    def test_failed_independent_central_scan_fails(self):
        c, reg, central, gg = scenario()
        central["complete"] = False
        with self.assertRaisesRegex(ValueError, "pagination not complete"):
            sg.validate_snapshot(c, reg, central, gg)

    def test_mismatched_central_90d_fails(self):
        c, reg, central, gg = scenario()
        gg["stableIdCount"] = 120
        with self.assertRaisesRegex(ValueError, "disagrees materially"):
            sg.validate_snapshot(c, reg, central, gg)

    def test_unresolved_exact_links_fails(self):
        c, reg, central, gg = scenario()
        c["supportLinkResolution"]["seoulExact"] = 19
        with self.assertRaisesRegex(ValueError, "exact support"):
            sg.validate_snapshot(c, reg, central, gg)

    def test_critical_verification_fails(self):
        c, reg, central, gg = scenario()
        c["verification"]["state"] = "critical"
        with self.assertRaisesRegex(ValueError, "critical"):
            sg.validate_snapshot(c, reg, central, gg)

class UnifiedRegionalGateTests(unittest.TestCase):
    def data(self):
        registry = {"gyeonggi": {}, "seoul": {}, "incheon": {}}
        meta = {
            "policy": "seoul-gyeonggi-isolated-verified-v1", "state": "verified",
            "refreshedRegions": ["경기", "서울"], "refreshedOfficialSourceCount": 38,
            "heldRegions": {"인천": {"state": "stale"}},
        }
        unified = {
            "officialSourceCount": 44,
            "sources": {"gyeonggi": {}, "seoul": {}, "incheon": {}},
            "jobs": [{"feedKind": "official", "sourceSurface": "official", "province": p}
                     for p in ("경기", "서울")],
            "regionalPublication": meta,
        }
        return registry, unified

    def invoke(self, registry, unified):
        with mock.patch.object(guard, "load_json", side_effect=lambda path: {
            "sources.json": registry, "unified_jobs.json": unified
        }[path]), mock.patch.object(guard, "official_source_count", return_value=44):
            guard.main()

    def test_verified_held_incheon_allows_two_region_display(self):
        self.invoke(*self.data())

    def test_stale_incheon_cannot_be_described_as_fresh(self):
        registry, unified = self.data()
        unified["jobs"].append({
            "feedKind": "official", "sourceSurface": "official", "province": "인천"
        })
        with self.assertRaisesRegex(SystemExit, "stale Incheon"):
            self.invoke(registry, unified)

    def test_unverified_held_status_fails_closed(self):
        registry, unified = self.data()
        unified["regionalPublication"]["heldRegions"]["인천"]["state"] = "fresh"
        with self.assertRaisesRegex(SystemExit, "not trusted"):
            self.invoke(registry, unified)

    def test_legacy_mode_still_requires_incheon(self):
        registry, unified = self.data()
        del unified["regionalPublication"]
        with self.assertRaisesRegex(SystemExit, "missing mandatory provinces"):
            self.invoke(registry, unified)


from datetime import datetime, timedelta, timezone
import seoul_gyeonggi_watchdog as scheduler


class ProtectedRegionalWatchdogTests(unittest.TestCase):
    NOW = datetime(2026, 11, 10, 1, 0, tzinfo=timezone.utc)

    def matching_regional_proof(self):
        generated = (self.NOW - timedelta(hours=2)).isoformat()
        counts = {"gyeonggi": 60, "seoul": 60}
        metadata = {
            "policy": scheduler.REGIONAL_POLICY,
            "state": "verified", "generatedAt": generated,
            "refreshedRegions": ["경기", "서울"],
            "refreshedOfficialSourceCount": 38,
            "heldRegions": {"인천": {"state": "stale"}},
            "officialJobs": counts,
        }
        report = {
            "policy": scheduler.REGIONAL_POLICY,
            "generatedAt": generated, "state": "verified",
            "counts": counts,
        }
        snapshot = {
            "regionalPublication": metadata, "officialSourceCount": 38,
            "sources": {"gyeonggi": {}, "seoul": {}},
            "jobs": [{"province": "경기" if i % 2 else "서울"}
                     for i in range(120)],
        }
        unified = {
            "regionalPublication": dict(metadata),
            "jobs": [{"feedKind": "official", "province": "경기"}
                     for _ in range(120)],
        }
        return report, snapshot, unified

    def test_prioritizes_region_snapshot_instead_of_broken_incheon_fast(self):
        action, _ = scheduler.decide("fast", {}, [], self.NOW)
        self.assertEqual(action, "seoul-gyeonggi")

    def test_does_not_dispatch_full_incheon_after_fresh_regional_snapshot(self):
        report, snapshot, unified = self.matching_regional_proof()
        action, _ = scheduler.decide("recovery", report, [], self.NOW,
                                     snapshot=snapshot, unified=unified)
        self.assertEqual(action, "skip-incheon-hold")

    def test_report_alone_does_not_prove_fresh_data(self):
        report, _, _ = self.matching_regional_proof()
        action, _ = scheduler.decide("fast", report, [], self.NOW)
        self.assertEqual(action, "seoul-gyeonggi")

    def test_mismatched_snapshot_fails_closed(self):
        report, snapshot, unified = self.matching_regional_proof()
        snapshot["jobs"].append({"province": "인천"})
        action, _ = scheduler.decide("fast", report, [], self.NOW,
                                     snapshot=snapshot, unified=unified)
        self.assertEqual(action, "seoul-gyeonggi")

    def test_verified_regional_data_but_unified_not_published_drains_backlog(self):
        report, snapshot, _ = self.matching_regional_proof()
        action, _ = scheduler.decide("private-jobteacher", report, [], self.NOW,
                                     snapshot=snapshot, unified={}, unified_runs=[])
        self.assertEqual(action, "unified")

    def test_unified_run_history_is_required_to_dispatch(self):
        report, snapshot, _ = self.matching_regional_proof()
        action, _ = scheduler.decide("private-jobteacher", report, [], self.NOW,
                                     snapshot=snapshot, unified={})
        self.assertEqual(action, "private-jobteacher")

    def test_running_unified_is_not_dispatched_again(self):
        report, snapshot, _ = self.matching_regional_proof()
        running = [{
            "event": "workflow_dispatch", "head_branch": "main",
            "status": "in_progress", "conclusion": None,
        }]
        action, _ = scheduler.decide("private-jobteacher", report, [], self.NOW,
                                     snapshot=snapshot, unified={}, unified_runs=running)
        self.assertEqual(action, "private-jobteacher")

    def test_recent_unified_failure_preserves_backoff(self):
        report, snapshot, _ = self.matching_regional_proof()
        failure = [{
            "event": "workflow_dispatch", "head_branch": "main",
            "status": "completed", "conclusion": "failure",
            "updated_at": (self.NOW - timedelta(minutes=10)).isoformat(),
        }]
        action, _ = scheduler.decide("private-jobteacher", report, [], self.NOW,
                                     snapshot=snapshot, unified={}, unified_runs=failure)
        self.assertEqual(action, "private-jobteacher")

    def test_successful_unified_attempt_after_snapshot_not_repeated(self):
        report, snapshot, _ = self.matching_regional_proof()
        success = [{
            "event": "workflow_dispatch", "head_branch": "main",
            "status": "completed", "conclusion": "success",
            "updated_at": (self.NOW - timedelta(minutes=5)).isoformat(),
        }]
        action, _ = scheduler.decide("private-jobteacher", report, [], self.NOW,
                                     snapshot=snapshot, unified={}, unified_runs=success)
        self.assertEqual(action, "private-jobteacher")


    def test_unified_fresh_marker_prevents_unnecessary_rebuild(self):
        report, snapshot, unified = self.matching_regional_proof()
        action, _ = scheduler.decide("private-jobteacher", report, [], self.NOW,
                                     snapshot=snapshot, unified=unified)
        self.assertEqual(action, "private-jobteacher")

    def test_unified_circuit_open_is_not_bypassed(self):
        report, snapshot, _ = self.matching_regional_proof()
        action, _ = scheduler.decide("skip-unified-circuit-open", report, [], self.NOW,
                                     snapshot=snapshot, unified={})
        self.assertEqual(action, "skip-unified-circuit-open")

    def test_region_proof_expired_requires_recollection(self):
        report, snapshot, unified = self.matching_regional_proof()
        expired = (self.NOW - timedelta(hours=8)).isoformat()
        report["generatedAt"] = expired
        snapshot["regionalPublication"]["generatedAt"] = expired
        unified["regionalPublication"]["generatedAt"] = expired
        action, _ = scheduler.decide("fast", report, [], self.NOW,
                                     snapshot=snapshot, unified=unified)
        self.assertEqual(action, "seoul-gyeonggi")

    def test_active_regional_run_blocks_duplicate(self):
        runs = [{"event": "workflow_dispatch", "head_branch": "main", "status": "in_progress"}]
        action, _ = scheduler.decide("fast", {}, runs, self.NOW)
        self.assertEqual(action, "skip-incheon-hold")

    def test_failed_regional_run_uses_six_hour_backoff(self):
        runs = [{
            "event": "workflow_dispatch", "head_branch": "main",
            "status": "completed", "conclusion": "failure",
            "updated_at": (self.NOW - timedelta(minutes=20)).isoformat()
        }]
        action, _ = scheduler.decide("fast", {}, runs, self.NOW)
        self.assertEqual(action, "skip-incheon-hold")

    def test_private_writer_continues_during_regional_failure_backoff(self):
        runs = [{
            "event": "workflow_dispatch", "head_branch": "main",
            "status": "completed", "conclusion": "failure",
            "updated_at": (self.NOW - timedelta(minutes=20)).isoformat()
        }]
        action, _ = scheduler.decide("private-jobteacher", {}, runs, self.NOW)
        self.assertEqual(action, "private-jobteacher")

    def test_existing_active_run_still_wins(self):
        action, _ = scheduler.decide("skip-active-run", {}, [], self.NOW)
        self.assertEqual(action, "skip-active-run")

    def test_failed_region_writer_can_retry_after_backoff(self):
        runs = [{
            "event": "workflow_dispatch", "head_branch": "main",
            "status": "completed", "conclusion": "failure",
            "updated_at": (self.NOW - timedelta(hours=7)).isoformat()
        }]
        action, _ = scheduler.decide("skip-fast-circuit-open", {}, runs, self.NOW)
        self.assertEqual(action, "seoul-gyeonggi")


if __name__ == "__main__":
    unittest.main()
