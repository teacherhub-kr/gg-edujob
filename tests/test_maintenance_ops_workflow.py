from pathlib import Path
import unittest


class MaintenanceOperationsWorkflowTests(unittest.TestCase):
    def test_manual_maintenance_targets_are_consolidated(self):
        text = Path(".github/workflows/maintenance-ops.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("schedule:", text)
        for target in (
            "frontend-performance",
            "normalize-collector-status",
            "operational-quality",
            "search-integrity",
            "service-health",
            "exact-link-integrity",
        ):
            self.assertIn(f"- {target}", text)

    def test_maintenance_workflow_does_not_dispatch_other_workflows(self):
        text = Path(".github/workflows/maintenance-ops.yml").read_text(encoding="utf-8")
        self.assertNotIn("/dispatches", text)
        self.assertNotIn("gh workflow run", text)

    def test_writer_concurrency_contracts_are_preserved(self):
        text = Path(".github/workflows/maintenance-ops.yml").read_text(encoding="utf-8")
        for group in (
            "metro-edujob-frontend",
            "metro-edujob-data",
            "metro-edujob-quality-audit",
            "metro-edujob-search-integrity",
            "metro-edujob-observability",
            "metro-edujob-exact-links",
        ):
            self.assertIn(group, text)


if __name__ == "__main__":
    unittest.main()
