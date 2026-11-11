"""Evidence-age status must not be confused with successful collection/row eligibility."""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from private_source_registry import (  # noqa: E402
    PRIVATE_SOURCES,
    PRIVATE_VERIFICATION_MAX_AGE_HOURS,
    source_verification_freshness,
)
from production_supervisor import PRIVATE_REFRESH_TARGETS  # noqa: E402


NOW = datetime(2026, 11, 11, 0, tzinfo=timezone.utc)


def report(hours):
    return {"generatedAt": (NOW - timedelta(hours=hours)).isoformat(),
            "healthy": True, "traversalComplete": True, "missingAfterCount": 0}


class PrivateSourceEvidenceFreshnessTests(unittest.TestCase):
    def get(self, key):
        return next(spec for spec in PRIVATE_SOURCES if spec["key"] == key)

    def test_thresholds_match_operational_scheduler(self):
        mapping = {
            "lessoninfo": "private-lessoninfo",
            "cleaneye": "private-foundation",
            "jobteacher": "private-jobteacher",
            "artmore": "private-artmore-candidate",
            "gonggonggangsa": "private-gonggonggangsa",
            "seekle": "private-seekle",
            "boramyc": "private-boramyc",
        }
        self.assertEqual(set(PRIVATE_VERIFICATION_MAX_AGE_HOURS), set(mapping))
        for key, control in mapping.items():
            self.assertEqual(PRIVATE_VERIFICATION_MAX_AGE_HOURS[key],
                             PRIVATE_REFRESH_TARGETS[control]["maxAgeHours"])

    def test_old_success_remains_stale_not_current(self):
        evidence = source_verification_freshness(self.get("lessoninfo"), report(25*24), now=NOW)
        self.assertEqual(evidence["state"], "stale")
        self.assertEqual(evidence["ageHours"], 600)
        self.assertEqual(evidence["maxAgeHours"], 6)

    def test_recent_success_is_fresh(self):
        evidence = source_verification_freshness(self.get("lessoninfo"), report(2), now=NOW)
        self.assertEqual(evidence["state"], "fresh")
        self.assertEqual(evidence["ageHours"], 2)

    def test_detail_proof_cannot_rejuvenate_old_traversal(self):
        evidence = source_verification_freshness(self.get("jobteacher"), report(18),
                                                 report(1), now=NOW)
        self.assertEqual(evidence["state"], "stale")
        self.assertEqual(evidence["ageHours"], 18)

    def test_old_detail_proof_also_stales_new_traversal(self):
        evidence = source_verification_freshness(self.get("jobteacher"), report(1),
                                                 report(18), now=NOW)
        self.assertEqual(evidence["state"], "stale")

    def test_missing_required_detail_proof_is_unknown(self):
        self.assertEqual(source_verification_freshness(
            self.get("jobteacher"), report(1), None, now=NOW)["state"], "unknown")

    def test_unknown_timestamp_never_claims_fresh(self):
        for value in (None, "", "2026-11-10 15:00:00", "not-a-date"):
            proof = {"generatedAt": value} if value is not None else {}
            self.assertEqual(source_verification_freshness(
                self.get("lessoninfo"), proof, now=NOW)["state"], "unknown")
        future = {"generatedAt": (NOW + timedelta(hours=1)).isoformat()}
        self.assertEqual(source_verification_freshness(
            self.get("lessoninfo"), future, now=NOW)["state"], "unknown")

    def test_source_specific_limits(self):
        self.assertEqual(source_verification_freshness(
            self.get("cleaneye"), report(20), now=NOW)["state"], "fresh")
        self.assertEqual(source_verification_freshness(
            self.get("seekle"), report(13), now=NOW)["state"], "stale")

    def test_no_source_data_mutation(self):
        prior=report(26)
        original=dict(prior)
        source_verification_freshness(self.get("lessoninfo"), prior, now=NOW)
        self.assertEqual(prior, original)


if __name__ == "__main__":
    unittest.main()
