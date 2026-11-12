"""Fail-closed publication contract for the isolated JobTeacher workflow."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class JobTeacherWorkflowContracts(unittest.TestCase):
    def test_failed_semantics_never_commit_candidate_dataset(self):
        text = (ROOT / ".github/workflows/update-jobteacher-jobs.yml").read_text(encoding="utf-8")
        commit_block = text.split("- name: Commit verified isolated dataset", 1)[1].split(
            "- name: Fail after preserving diagnostics", 1
        )[0]
        expected = (
            "if: steps.collect.outcome == 'success' && "
            "steps.detail_links.outcome == 'success' && "
            "steps.validate.outcome == 'success' && "
            "steps.promote.outcome == 'success'"
        )
        self.assertIn(expected, commit_block)
        self.assertNotIn("if: always()", commit_block)
        self.assertIn("git add jobteacher_jobs.json", commit_block)

    def test_failed_gate_still_fails_the_workflow(self):
        text = (ROOT / ".github/workflows/update-jobteacher-jobs.yml").read_text(encoding="utf-8")
        self.assertIn("- name: Fail after preserving diagnostics", text)
        self.assertIn("steps.promote.outcome != 'success'", text)
        self.assertIn("run: exit 1", text)


if __name__ == "__main__":
    unittest.main()
