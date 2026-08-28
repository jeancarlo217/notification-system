"""B7, the schedule decision: which warnings are owed, as a pure function.

Traces: foundation section 5 (thresholds and the catch-up rule), I1 (a sent pair is never owed
again), I3 (owed-ness derives from the given records and the given today, so missed days catch
up), I4 (the schedule follows the configured thresholds with no code change). No database, no
clock, no Django machinery (specs/testing.md, decisions versus effects).
"""

import datetime

from core.engine import OwedWarning, ServiceRecord, owed_warnings

THRESHOLDS = (30, 7, 0)


def _active_service(
    service_id: int = 1, due: datetime.date = datetime.date(2027, 1, 31)
) -> ServiceRecord:
    return ServiceRecord(id=service_id, due_date=due, status="active")


def test_a_threshold_whose_trigger_date_is_today_is_owed() -> None:
    """Foundation section 5: the 30 day warning triggers exactly 30 days before the due date."""
    services = [_active_service(due=datetime.date(2027, 1, 31))]

    owed = owed_warnings(
        services, thresholds=THRESHOLDS, today=datetime.date(2027, 1, 1), sent=frozenset()
    )

    assert set(owed) == {OwedWarning(service_id=1, threshold=30)}


def test_a_threshold_whose_trigger_date_has_not_arrived_owes_nothing() -> None:
    """Foundation section 5, the quiet side: a future trigger date owes nothing yet."""
    services = [_active_service(due=datetime.date(2027, 1, 31))]

    owed = owed_warnings(
        services, thresholds=THRESHOLDS, today=datetime.date(2026, 12, 31), sent=frozenset()
    )

    assert set(owed) == set()


def test_missed_days_owe_every_passed_threshold_never_sent() -> None:
    """I3: on the due date with no runs before, all three trigger dates have passed unsent."""
    services = [_active_service(due=datetime.date(2027, 1, 10))]

    owed = owed_warnings(
        services, thresholds=THRESHOLDS, today=datetime.date(2027, 1, 10), sent=frozenset()
    )

    assert set(owed) == {
        OwedWarning(service_id=1, threshold=30),
        OwedWarning(service_id=1, threshold=7),
        OwedWarning(service_id=1, threshold=0),
    }


def test_a_sent_warning_is_never_owed_again() -> None:
    """I1, the decision half: a (service, threshold) pair already sent leaves the schedule."""
    services = [_active_service(due=datetime.date(2027, 1, 10))]

    owed = owed_warnings(
        services,
        thresholds=THRESHOLDS,
        today=datetime.date(2027, 1, 10),
        sent=frozenset({(1, 30), (1, 7)}),
    )

    assert set(owed) == {OwedWarning(service_id=1, threshold=0)}


def test_a_completed_service_owes_nothing() -> None:
    """Foundation sections 3 and 5: warnings are computed only for active services."""
    services = [ServiceRecord(id=1, due_date=datetime.date(2027, 1, 10), status="completed")]

    owed = owed_warnings(
        services, thresholds=THRESHOLDS, today=datetime.date(2027, 1, 10), sent=frozenset()
    )

    assert set(owed) == set()


def test_the_schedule_follows_the_configured_thresholds_with_no_code_change() -> None:
    """I4: two threshold configurations, two schedules, same records and same today."""
    services = [_active_service(due=datetime.date(2027, 1, 31))]
    today = datetime.date(2027, 1, 5)

    company_schedule = owed_warnings(services, thresholds=(30, 7, 0), today=today, sent=frozenset())
    other_schedule = owed_warnings(services, thresholds=(45, 10), today=today, sent=frozenset())

    assert set(company_schedule) == {OwedWarning(service_id=1, threshold=30)}
    assert set(other_schedule) == {OwedWarning(service_id=1, threshold=45)}


def test_each_service_is_scheduled_independently() -> None:
    """Foundation section 5: the rule applies per service, from each service's own due date."""
    services = [
        _active_service(service_id=1, due=datetime.date(2027, 1, 31)),
        _active_service(service_id=2, due=datetime.date(2027, 2, 28)),
    ]

    owed = owed_warnings(
        services, thresholds=THRESHOLDS, today=datetime.date(2027, 1, 1), sent=frozenset()
    )

    assert set(owed) == {OwedWarning(service_id=1, threshold=30)}
