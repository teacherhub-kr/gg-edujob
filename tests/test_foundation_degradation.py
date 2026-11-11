import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, "scripts")
import mark_foundation_degraded as degraded


class FoundationDegradationTests(unittest.TestCase):
    def write_json(self, path: Path, data):
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def test_degradation_marks_metadata_without_mutating_rows(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            unified = root / "unified_jobs.json"
            search = root / "unified_search_report.json"
            coverage = root / "cultural_foundation_coverage_report.json"
            rows = [
                {"sourceIdentity": "official:1", "feedKind": "official", "sourceSurface": "education"},
                {"sourceIdentity": "foundation:1", "feedKind": "official", "sourceSurface": "cultural-foundation"},
            ]
            self.write_json(unified, {"jobs": rows, "counts": {"total": 2}})
            self.write_json(search, {"publishedJobs": 2})
            self.write_json(
                coverage,
                {
                    "healthy": False,
                    "generatedAt": "2026-10-01T22:00:00+09:00",
                    "coverageGapCount": 1,
                    "failedAvailableComponents": [],
                },
            )
            with patch.object(degraded, "UNIFIED", unified), patch.object(degraded, "SEARCH_REPORT", search), patch.object(degraded, "COVERAGE_REPORT", coverage):
                result = degraded.mark_foundation_degraded()

            after = json.loads(unified.read_text(encoding="utf-8"))
            report = json.loads(search.read_text(encoding="utf-8"))
            self.assertEqual(after["jobs"], rows)
            self.assertEqual(after["degradedSections"], ["foundation"])
            self.assertFalse(after["sectionHealth"]["foundation"]["healthy"])
            self.assertEqual(after["sectionHealth"]["foundation"]["coverageGapCount"], 1)
            self.assertEqual(report["degradedSections"], ["foundation"])
            self.assertFalse(report["foundationCoverageHealthy"])
            self.assertEqual(report["foundationCoverageGapCount"], 1)
            self.assertEqual(result["jobsUnchanged"], True)

    def test_healthy_coverage_cannot_be_marked_degraded(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            unified = root / "unified_jobs.json"
            search = root / "unified_search_report.json"
            coverage = root / "cultural_foundation_coverage_report.json"
            self.write_json(unified, {"jobs": []})
            self.write_json(search, {})
            self.write_json(coverage, {"healthy": True, "coverageGapCount": 0})
            with patch.object(degraded, "UNIFIED", unified), patch.object(degraded, "SEARCH_REPORT", search), patch.object(degraded, "COVERAGE_REPORT", coverage):
                with self.assertRaises(ValueError):
                    degraded.mark_foundation_degraded()

    def test_workflow_allows_degraded_foundation_only_after_core_validation(self):
        workflow = Path(".github/workflows/unified-search.yml").read_text(encoding="utf-8")
        self.assertIn("Mark foundation section degraded without blocking core official publication", workflow)
        self.assertIn("steps.prepare_publication.outcome == 'success'", workflow)
        self.assertIn("steps.crosscheck.outcome == 'success'", workflow)
        self.assertIn("(steps.foundation_reconcile.outcome == 'success' || steps.foundation_degrade.outcome == 'success')", workflow)
        self.assertIn("(steps.foundation_reconcile.outcome == 'failure' && steps.foundation_degrade.outcome != 'success')", workflow)


if __name__ == "__main__":
    unittest.main()
