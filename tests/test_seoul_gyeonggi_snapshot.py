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


if __name__ == "__main__":
    unittest.main()
