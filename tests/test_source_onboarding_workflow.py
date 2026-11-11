from pathlib import Path
import unittest


class SourceOnboardingWorkflowTests(unittest.TestCase):
    def test_all_probe_targets_are_consolidated_without_automatic_trigger(self):
        text = Path(".github/workflows/source-onboarding.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("schedule:", text)
        targets = (
            "support-links",
            "artmore-filter-payload",
            "artmore-public-js-handlers",
            "artmore-region-commit-v2",
            "artmore-region-commit-v3",
            "artmore-region-hierarchy",
            "artmore-region-popup-commit",
            "artmore-region-semantics",
            "artmore-region-ui-v2",
            "artmore-region-ui-v3",
            "artmore-visible-region-controls",
            "artmore-browser",
            "gonggonggangsa",
            "hunjang",
            "jobteacher",
            "public-instructor-api",
            "public-instructor",
        )
        for target in targets:
            self.assertIn(f"- {target}", text)

    def test_onboarding_keeps_candidates_out_of_publication(self):
        text = Path(".github/workflows/source-onboarding.yml").read_text(encoding="utf-8")
        self.assertNotIn("unified-search.yml", text)
        self.assertNotIn("update-jobs.yml", text)
        self.assertNotIn("/dispatches", text)


if __name__ == "__main__":
    unittest.main()
