"""The deadline a start date and a term compute to (owner decision, 2026-08-31).

A pure decision: plain data in, plain data out, no database and no clock (specs/testing.md), so
``core/models.py`` can import it the way it imports ``core.identity`` and without a cycle.
"""

import datetime


def due_date_from(start_date: datetime.date, term_days: int) -> datetime.date:
    """The day a service that started on ``start_date`` and runs for ``term_days`` is owed.

    A term of zero is due on its start date, so a stored deadline reproduces itself exactly.
    """
    return start_date + datetime.timedelta(days=term_days)
