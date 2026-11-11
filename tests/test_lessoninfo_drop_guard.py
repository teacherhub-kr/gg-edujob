"""Regression tests for fail-closed Lessoninfo ID-evidenced population drop."""
import unittest

from scripts.lessoninfo_drop_guard import validate_population_drop


def fixture(reason="stale-without-deadline", missing=False, date="2026-10-09"):
    old_rows = [
        {"sourceIdentity": f"board:test:{i}", "sourceSurface": "afterschool-nulbom"}
        for i in range(27)
    ]
    new_rows = [
        {
            "sourceIdentity": f"board:test:{i}",
            "sourceSurface": "afterschool-nulbom",
            "isCurrent": True,
            "classificationReason": "active",
            "registered": "2026-10-15",
        }
        for i in range(11)
    ]
    new_rows.extend(
        {
            "sourceIdentity": f"board:test:{i}",
            "sourceSurface": "afterschool-nulbom",
            "isCurrent": False,
            "classificationReason": reason,
            "registered": date,
        }
        for i in range(11, 27) if not (missing and i == 26)
    )
    new_rows.extend(
        {
            "sourceIdentity": f"board:new:{i}",
            "sourceSurface": "afterschool-nulbom",
            "isCurrent": True,
            "classificationReason": "active",
            "registered": "2026-11-01",
        }
        for i in range(4)
    )
    prev = {"healthy": True, "activeIdCount": 27, "perSurfaceActive": {"afterschool-nulbom": 27}}
    cur = {
        "healthy": True, "traversalComplete": True, "detailErrorCount": 0,
        "missingAfterCount": 0, "generatedAt": "2026-11-11T08:54:46+09:00",
        "activeIdCount": 15, "candidateIdCount": len(new_rows),
        "perSurfaceActive": {"afterschool-nulbom": 15},
    }
    return prev, cur, {"jobs": old_rows}, {"jobs": new_rows}


class TestLessoninfoDropGuard(unittest.TestCase):
    def test_30_day_policy_explains_drop_without_disabling_guard(self):
        result = validate_population_drop(*fixture())
        self.assertEqual(len(result), 1)
        self.assertIn("retired=16", result[0])

    def test_missing_old_id_is_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "unexplained"):
            validate_population_drop(*fixture(missing=True))

    def test_route_mismatch_is_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "unexplained"):
            validate_population_drop(*fixture(reason="detail-route-mismatch"))

    def test_fresh_record_cannot_be_falsely_staled(self):
        with self.assertRaisesRegex(ValueError, "not-older"):
            validate_population_drop(*fixture(date="2026-11-01"))

    def test_incomplete_scan_is_fail_closed(self):
        prev, cur, old, current = fixture()
        cur["traversalComplete"] = False
        with self.assertRaisesRegex(ValueError, "incomplete"):
            validate_population_drop(prev, cur, old, current)

    def test_no_large_drop_preserves_existing_behavior(self):
        prev, cur, old, current = fixture()
        cur["perSurfaceActive"]["afterschool-nulbom"] = 17
        self.assertEqual(validate_population_drop(prev, cur, old, current), [])

    def test_closed_marker_is_explicit_retirement(self):
        result = validate_population_drop(*fixture(reason="closed-marker"))
        self.assertIn("closed-marker", result[0])


if __name__ == "__main__":
    unittest.main()
