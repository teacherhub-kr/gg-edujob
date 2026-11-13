"""Interpret source-visible, yearless JobTeacher recruiting deadlines.

These rules ONLY apply to jobs already found in the current public listing.
Do not guess arbitrary years or infer 'open' status from a historical detail page.
"""
from __future__ import annotations

from datetime import date


def resolve_yearless_deadline(today: date, month: int, day: int) -> date | None:
    """Return a narrow date interpretation, or None for an invalid calendar day.

    JobTeacher displays e.g. "~01.07" without a year. In Nov/Dec only,
    a currently displayed January/February deadline refers to the next
    calendar year. Other dates retain the current year, so prior deadlines
    still fail the existing expired-date gate. Do not assume a 12-month cycle.
    """
    rollover = today.month in (11, 12) and month in (1, 2)
    year = today.year + 1 if rollover else today.year
    try:
        return date(year, month, day)
    except ValueError:
        return None
