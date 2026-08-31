"""The deadline a start date and a term compute to, as a pure decision.

Traces: the owner decision of 2026-08-31 (an employee types a date and a number of days, and the
deadline is the first plus the second), I4 (the term is data on the record, never a literal in
code) and specs/testing.md (a decision is plain data in and plain data out, with no clock and no
database, and it carries the bulk of the tests).
"""

import datetime

from core.terms import due_date_from


def test_a_term_of_twenty_days_from_the_fifth_is_due_on_the_twenty_fifth() -> None:
    """Owner decision, 2026-08-31: the 5th with a term of 20 days is due 20 days after the 5th."""
    assert due_date_from(datetime.date(2026, 9, 5), 20) == datetime.date(2026, 9, 25)


def test_a_term_of_zero_days_is_due_on_the_day_it_starts() -> None:
    """Owner decision, 2026-08-31: a service with nothing to run is owed the day it is taken."""
    assert due_date_from(datetime.date(2026, 9, 5), 0) == datetime.date(2026, 9, 5)


def test_a_term_of_one_day_is_due_the_day_after_it_starts() -> None:
    """Owner decision, 2026-08-31: the term counts days forward, so one day is the next day and
    never the same day counted twice."""
    assert due_date_from(datetime.date(2026, 9, 5), 1) == datetime.date(2026, 9, 6)


def test_a_term_crosses_the_end_of_a_month() -> None:
    """Owner decision, 2026-08-31: the term is a count of days, so a month boundary is arithmetic
    and never a special case."""
    assert due_date_from(datetime.date(2026, 1, 20), 20) == datetime.date(2026, 2, 9)


def test_a_term_crosses_the_end_of_a_year() -> None:
    """Owner decision, 2026-08-31: a December start with a term that outlives the year lands in
    the next one."""
    assert due_date_from(datetime.date(2026, 12, 20), 20) == datetime.date(2027, 1, 9)


def test_a_term_counts_the_extra_day_of_a_leap_year() -> None:
    """Owner decision, 2026-08-31: 2028 has a 29th of February and the count includes it, so a
    ten day term from the 20th lands on the 1st of March rather than the 2nd."""
    assert due_date_from(datetime.date(2028, 2, 20), 10) == datetime.date(2028, 3, 1)


def test_a_term_of_a_full_year_lands_a_year_later() -> None:
    """Owner decision, 2026-08-31: the licence renewals this tool tracks are yearly, so 365 days
    is the ordinary case rather than an extreme one."""
    assert due_date_from(datetime.date(2026, 3, 1), 365) == datetime.date(2027, 3, 1)


def test_the_deadline_is_a_date_and_never_a_moment_in_time() -> None:
    """Foundation section 5: thresholds are measured in days, so the decision returns a day."""
    computed = due_date_from(datetime.date(2026, 9, 5), 20)

    assert type(computed) is datetime.date


def test_a_zero_term_reproduces_a_stored_due_date_exactly() -> None:
    """I1 and I3: the backfill of the existing rows sets the start date to the due date already
    stored with a term of zero, so every deadline lands on the same day it was on. If this ever
    stopped holding, every backfilled row would move and re fire or lose a warning."""
    stored = datetime.date(2026, 8, 28)

    assert due_date_from(stored, 0) == stored
