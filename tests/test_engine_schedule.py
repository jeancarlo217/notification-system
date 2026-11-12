"""B27, the two schedule decisions: which lines the list carries, and whether a list is owed now.

Traces: foundation section 4 (every active service, overdue ones included, nearest deadline
first), section 5 (one list a day from the configured send time, retried hourly), I1 (a day whose
list was delivered owes nothing more), I2 (a failed or stuck attempt is owed again an hour later),
I3 (owed-ness derives from the given clock and the given record, so a late run still owes the
list), I4 (the send time is configuration). No database, no real clock, no Django machinery
(specs/testing.md, decisions versus effects). The rule numbers are the eight of backlog B27.
"""

import datetime
from zoneinfo import ZoneInfo

from core.engine import DispatchRecord, ListLine, ServiceRecord, list_is_owed, list_lines

CAMPO_GRANDE = ZoneInfo("America/Campo_Grande")
UTC = datetime.UTC
SEVEN = datetime.time(7, 0)
TODAY = datetime.date(2026, 12, 15)


def _local(hour: int, minute: int = 0) -> datetime.datetime:
    return datetime.datetime(2026, 12, 15, hour, minute, tzinfo=CAMPO_GRANDE)


def _service(
    client: str = "Fazenda Boa Vista",
    due: datetime.date = datetime.date(2026, 12, 25),
    status: str = "active",
    service: str = "Licenciamentos Ambientais",
) -> ServiceRecord:
    return ServiceRecord(client=client, service=service, due_date=due, status=status)


def test_every_active_service_is_one_line_carrying_its_days_remaining() -> None:
    """B27 rule 1, foundation section 4: no threshold selects anything, a far deadline is listed."""
    services = [_service(due=datetime.date(2027, 6, 30))]

    lines = list_lines(services, today=TODAY)

    assert lines == (
        ListLine(
            client="Fazenda Boa Vista",
            service="Licenciamentos Ambientais",
            due_date=datetime.date(2027, 6, 30),
            days_remaining=197,
        ),
    )


def test_an_overdue_service_is_listed_with_a_negative_distance() -> None:
    """B27 rule 1: overdue services stay in the list until a human closes them."""
    services = [_service(due=datetime.date(2026, 12, 12))]

    lines = list_lines(services, today=TODAY)

    assert [line.days_remaining for line in lines] == [-3]


def test_a_completed_service_is_never_listed() -> None:
    """B27 rule 1, foundation section 3: only active services enter the list."""
    services = [
        _service(client="Fazenda Boa Vista", status="completed"),
        _service(client="Sitio Santa Fe"),
    ]

    lines = list_lines(services, today=TODAY)

    assert [line.client for line in lines] == ["Sitio Santa Fe"]


def test_the_lines_are_ordered_by_due_date_nearest_first() -> None:
    """B27 rule 2: the nearest deadline is read first, whatever order the records arrive in."""
    services = [
        _service(client="Longe", due=datetime.date(2027, 3, 1)),
        _service(client="Vencido", due=datetime.date(2026, 12, 1)),
        _service(client="Perto", due=datetime.date(2026, 12, 20)),
    ]

    lines = list_lines(services, today=TODAY)

    assert [line.client for line in lines] == ["Vencido", "Perto", "Longe"]


def test_services_due_on_the_same_day_are_ordered_by_client() -> None:
    """B27 rule 2: due date ascending, then client."""
    services = [
        _service(client="Sitio Santa Fe"),
        _service(client="Fazenda Boa Vista"),
    ]

    lines = list_lines(services, today=TODAY)

    assert [line.client for line in lines] == ["Fazenda Boa Vista", "Sitio Santa Fe"]


def test_no_active_service_means_no_line() -> None:
    """B27 rule 3, the decision half: an empty registry has nothing to list."""
    assert list_lines([_service(status="completed")], today=TODAY) == ()


def test_nothing_is_owed_a_minute_before_the_send_time() -> None:
    """B27 rule 4, the quiet side: at 06:59 no list is owed."""
    owed = list_is_owed(now=_local(6, 59), send_time=SEVEN, timezone=CAMPO_GRANDE, dispatch=None)

    assert owed is False


def test_the_list_is_owed_at_the_send_time() -> None:
    """B27 rule 4: at 07:00, with no list delivered today, the list is owed."""
    owed = list_is_owed(now=_local(7, 0), send_time=SEVEN, timezone=CAMPO_GRANDE, dispatch=None)

    assert owed is True


def test_the_send_time_is_read_in_the_configured_zone_and_never_in_the_clocks_own() -> None:
    """B27 rule 4, foundation section 5: a UTC host is four hours ahead of Mato Grosso do Sul, so
    07:00 on its own clock is three in the morning there and nothing is owed yet."""
    seven_on_a_utc_host = datetime.datetime(2026, 12, 15, 7, 0, tzinfo=UTC)
    seven_in_campo_grande = datetime.datetime(2026, 12, 15, 11, 0, tzinfo=UTC)

    early = list_is_owed(
        now=seven_on_a_utc_host, send_time=SEVEN, timezone=CAMPO_GRANDE, dispatch=None
    )
    on_time = list_is_owed(
        now=seven_in_campo_grande, send_time=SEVEN, timezone=CAMPO_GRANDE, dispatch=None
    )

    assert early is False
    assert on_time is True


def test_a_run_late_in_the_day_still_owes_the_list() -> None:
    """I3, B27 rule 7: a host that was down at seven owes the list whenever it comes back."""
    owed = list_is_owed(now=_local(22, 30), send_time=SEVEN, timezone=CAMPO_GRANDE, dispatch=None)

    assert owed is True


def test_a_day_whose_list_was_delivered_owes_nothing_more() -> None:
    """I1, B27 rule 5, the decision half: a sent record for today ends the day."""
    sent = DispatchRecord(state="sent", last_attempt_at=_local(7, 0))

    owed = list_is_owed(now=_local(15, 0), send_time=SEVEN, timezone=CAMPO_GRANDE, dispatch=sent)

    assert owed is False


def test_a_failed_list_is_not_owed_again_before_an_hour_has_passed() -> None:
    """B27 rule 6, the quiet side: fifty nine minutes after a failure nothing is attempted."""
    failed = DispatchRecord(state="failed", last_attempt_at=_local(7, 0))

    owed = list_is_owed(now=_local(7, 59), send_time=SEVEN, timezone=CAMPO_GRANDE, dispatch=failed)

    assert owed is False


def test_a_failed_list_is_owed_again_an_hour_after_its_last_attempt() -> None:
    """I2, B27 rule 6: a failure is retried every hour until one attempt is accepted."""
    failed = DispatchRecord(state="failed", last_attempt_at=_local(7, 0))

    owed = list_is_owed(now=_local(8, 0), send_time=SEVEN, timezone=CAMPO_GRANDE, dispatch=failed)

    assert owed is True


def test_a_list_left_pending_is_not_owed_again_before_an_hour_has_passed() -> None:
    """B27 rule 6, the quiet side: a pending record may be a send still in flight."""
    pending = DispatchRecord(state="pending", last_attempt_at=_local(7, 0))

    owed = list_is_owed(now=_local(7, 59), send_time=SEVEN, timezone=CAMPO_GRANDE, dispatch=pending)

    assert owed is False


def test_a_list_left_pending_by_a_run_that_died_is_owed_again_after_an_hour() -> None:
    """I2, B27 rule 6: a pending that never resolves would be a silent terminal state."""
    pending = DispatchRecord(state="pending", last_attempt_at=_local(7, 0))

    owed = list_is_owed(now=_local(8, 0), send_time=SEVEN, timezone=CAMPO_GRANDE, dispatch=pending)

    assert owed is True


def test_two_configured_send_times_answer_one_instant_differently() -> None:
    """I4 acceptance: the send time is data, so the same instant is owed under one and not the
    other with no code change."""
    now = _local(8, 0)

    at_seven = list_is_owed(
        now=now, send_time=datetime.time(7, 0), timezone=CAMPO_GRANDE, dispatch=None
    )
    at_nine = list_is_owed(
        now=now, send_time=datetime.time(9, 0), timezone=CAMPO_GRANDE, dispatch=None
    )

    assert at_seven is True
    assert at_nine is False
