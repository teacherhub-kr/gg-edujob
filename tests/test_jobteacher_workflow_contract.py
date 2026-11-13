"""Fail-closed publication contract for the isolated JobTeacher workflow."""
from pathlib import Path
from datetime import date
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from jobteacher_deadline_semantics import resolve_yearless_deadline


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

    def test_november_current_listing_january_rollover(self):
        # A current public listing uses ~01.07 without a year.
        self.assertEqual(
            resolve_yearless_deadline(date(2026, 11, 13), 1, 7),
            date(2027, 1, 7),
        )
        self.assertEqual(
            resolve_yearless_deadline(date(2026, 12, 28), 2, 28),
            date(2027, 2, 28),
        )

    def test_non_new_year_deadlines_do_not_roll_forward(self):
        # Past October in November remains expired; no arbitrary 1-year extension.
        self.assertEqual(
            resolve_yearless_deadline(date(2026, 11, 13), 10, 1),
            date(2026, 10, 1),
        )
        self.assertEqual(
            resolve_yearless_deadline(date(2026, 3, 1), 1, 7),
            date(2026, 1, 7),
        )
        # December deadlines viewed in January are in this calendar year.
        self.assertEqual(
            resolve_yearless_deadline(date(2027, 1, 2), 12, 20),
            date(2027, 12, 20),
        )

    def test_invalid_date_and_leap_day(self):
        self.assertIsNone(resolve_yearless_deadline(date(2026, 11, 13), 2, 30))
        self.assertEqual(
            resolve_yearless_deadline(date(2027, 12, 1), 2, 29),
            date(2028, 2, 29),
        )

    def test_workflow_routes_date_check_through_resolver(self):
        text = (ROOT / ".github/workflows/update-jobteacher-jobs.yml").read_text(encoding="utf-8")
        self.assertIn("from jobteacher_deadline_semantics import resolve_yearless_deadline", text)
        self.assertIn("end=resolve_yearless_deadline(today,month,day)", text)
        self.assertIn("bad.append((j.get('sourceIdentity'),'expired-deadline',deadline))", text)
        self.assertIn("assert not bad", text)

    def test_failed_gate_still_fails_the_workflow(self):
        text = (ROOT / ".github/workflows/update-jobteacher-jobs.yml").read_text(encoding="utf-8")
        self.assertIn("- name: Fail after preserving diagnostics", text)
        self.assertIn("steps.promote.outcome != 'success'", text)
        self.assertIn("run: exit 1", text)


if __name__ == "__main__":
    unittest.main()
