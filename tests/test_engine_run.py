"""B27, the daily engine run: effects against the database through the provider interface.

Traces: foundation section 2 (truth lives in persisted records, outcomes written back), sections
4 and 5 v0.6 (one list of every open service a day, from the send time, retried hourly), I1 (one
day, one list), I2 (a rejected send is a visible failed state, retried an hour later), I3 (a run
after missed days sends one list, today's). The provider is faked at its interface and the clock
is the ``now`` argument; no network, no real time (specs/testing.md). The rule numbers are the
eight of backlog B27.
"""

import datetime
import logging

import pytest
from django.test import override_settings

from core.engine import run_daily_engine
from core.models import Dispatch
from tests.builders import a_service
from tests.configuration import TEST_DEADLINER, local
from tests.fakes import FakeProvider

pytestmark = pytest.mark.django_db

SERVICE = "Licenciamentos Ambientais"


@override_settings(DEADLINER=TEST_DEADLINER)
def test_one_day_is_carried_by_one_list_and_the_next_day_by_another() -> None:
    """I1 acceptance: twice past the send time, one message and then none; at the next day's
    send time, a second message."""
    a_service(due_date=datetime.date(2026, 12, 25))
    provider = FakeProvider()

    run_daily_engine(provider=provider, now=local(2026, 12, 18, 7, 0))
    first_run = len(provider.deliveries)
    run_daily_engine(provider=provider, now=local(2026, 12, 18, 7, 1))
    second_run = len(provider.deliveries)
    run_daily_engine(provider=provider, now=local(2026, 12, 19, 7, 0))

    assert first_run == 1
    assert second_run == 1
    assert len(provider.deliveries) == 2
    assert Dispatch.objects.filter(state="sent").count() == 2


@override_settings(DEADLINER=TEST_DEADLINER)
def test_the_list_carries_every_active_service_once_nearest_deadline_first() -> None:
    """I1 and B27 rules 1 and 2: each active service is one line of the one message, overdue
    ones included, ordered by due date."""
    a_service(client="Longe", due_date=datetime.date(2027, 6, 30))
    a_service(client="Vencido", due_date=datetime.date(2026, 12, 15))
    a_service(client="Perto", due_date=datetime.date(2026, 12, 19))
    provider = FakeProvider()

    run_daily_engine(provider=provider, now=local(2026, 12, 18, 7, 0))

    assert provider.deliveries == [
        "2026-12-18|3\n"
        f"Vencido|{SERVICE}|2026-12-15|3 ago\n"
        f"Perto|{SERVICE}|2026-12-19|tomorrow\n"
        f"Longe|{SERVICE}|2027-06-30|in 194"
    ]


@override_settings(DEADLINER=TEST_DEADLINER)
def test_a_completed_service_is_never_in_the_list() -> None:
    """B27 rule 1, foundation section 3: only active services enter the list."""
    a_service(client="Concluido", due_date=datetime.date(2026, 12, 20), status="completed")
    a_service(client="Aberto", due_date=datetime.date(2026, 12, 25))
    provider = FakeProvider()

    run_daily_engine(provider=provider, now=local(2026, 12, 18, 7, 0))

    assert provider.deliveries == [f"2026-12-18|1\nAberto|{SERVICE}|2026-12-25|in 7"]


@override_settings(DEADLINER=TEST_DEADLINER)
def test_a_registry_with_no_active_service_sends_nothing_and_records_nothing() -> None:
    """B27 rule 3: no provider call and no dispatch row."""
    a_service(due_date=datetime.date(2026, 12, 25), status="completed")
    provider = FakeProvider()

    run_daily_engine(provider=provider, now=local(2026, 12, 18, 7, 0))

    assert provider.deliveries == []
    assert Dispatch.objects.count() == 0


@override_settings(DEADLINER=TEST_DEADLINER)
def test_nothing_is_sent_before_the_send_time() -> None:
    """B27 rule 4, I3 acceptance, the quiet side: a run at six of a day with no list sends
    nothing and records nothing."""
    a_service(due_date=datetime.date(2026, 12, 25))
    provider = FakeProvider()

    run_daily_engine(provider=provider, now=local(2026, 12, 18, 6, 0))

    assert provider.deliveries == []
    assert Dispatch.objects.count() == 0


@override_settings(DEADLINER=TEST_DEADLINER)
def test_a_run_after_missed_days_sends_one_list_and_it_is_todays() -> None:
    """I3 acceptance, B27 rule 7: three days with no run, then one run at ten; one message,
    listing every active service, recorded against the day it was sent on."""
    a_service(client="Fazenda Boa Vista", due_date=datetime.date(2026, 12, 25))
    a_service(client="Sitio Santa Fe", due_date=datetime.date(2026, 12, 30))
    provider = FakeProvider()

    run_daily_engine(provider=provider, now=local(2026, 12, 21, 10, 0))

    assert provider.deliveries == [
        "2026-12-21|2\n"
        f"Fazenda Boa Vista|{SERVICE}|2026-12-25|in 4\n"
        f"Sitio Santa Fe|{SERVICE}|2026-12-30|in 9"
    ]
    assert [dispatch.local_date for dispatch in Dispatch.objects.all()] == [
        datetime.date(2026, 12, 21)
    ]


@override_settings(DEADLINER=TEST_DEADLINER)
def test_a_rejected_send_leaves_the_days_list_failed() -> None:
    """I2 acceptance, first half: the rejection is a persisted, visible state."""
    a_service(due_date=datetime.date(2026, 12, 25))

    run_daily_engine(provider=FakeProvider(accept=False), now=local(2026, 12, 18, 7, 0))

    dispatch = Dispatch.objects.get(local_date=datetime.date(2026, 12, 18))
    assert dispatch.state == "failed"
    assert dispatch.last_attempt_at == local(2026, 12, 18, 7, 0)


@override_settings(DEADLINER=TEST_DEADLINER)
def test_a_failed_list_is_left_alone_for_an_hour_and_then_tried_again() -> None:
    """I2 acceptance, B27 rule 6: a run less than an hour later does nothing, a run an hour
    later attempts the same day's list through the same row."""
    a_service(due_date=datetime.date(2026, 12, 25))
    run_daily_engine(provider=FakeProvider(accept=False), now=local(2026, 12, 18, 7, 0))
    accepting = FakeProvider()

    run_daily_engine(provider=accepting, now=local(2026, 12, 18, 7, 59))
    too_soon = len(accepting.deliveries)
    run_daily_engine(provider=accepting, now=local(2026, 12, 18, 8, 0))

    assert too_soon == 0
    assert len(accepting.deliveries) == 1
    dispatch = Dispatch.objects.get()
    assert dispatch.local_date == datetime.date(2026, 12, 18)
    assert dispatch.state == "sent"
    assert dispatch.last_attempt_at == local(2026, 12, 18, 8, 0)


@override_settings(DEADLINER=TEST_DEADLINER)
def test_a_list_left_pending_by_a_run_that_died_is_retried_by_the_same_rule() -> None:
    """I2, B27 rule 6: a pending row is not a terminal state; an hour after its last attempt the
    list is sent through that row and never through a second one (I1)."""
    a_service(due_date=datetime.date(2026, 12, 25))
    Dispatch.objects.create(
        local_date=datetime.date(2026, 12, 18),
        service_count=1,
        last_attempt_at=local(2026, 12, 18, 7, 0),
    )
    provider = FakeProvider()

    run_daily_engine(provider=provider, now=local(2026, 12, 18, 7, 30))
    too_soon = len(provider.deliveries)
    run_daily_engine(provider=provider, now=local(2026, 12, 18, 8, 0))

    assert too_soon == 0
    assert len(provider.deliveries) == 1
    assert Dispatch.objects.get().state == "sent"


@override_settings(DEADLINER=TEST_DEADLINER)
def test_yesterdays_failure_is_not_resent_and_stays_on_record() -> None:
    """Foundation section 5: a list whose every attempt failed is replaced by the next morning's,
    and yesterday's failure stays visible (I2)."""
    a_service(due_date=datetime.date(2026, 12, 25))
    run_daily_engine(provider=FakeProvider(accept=False), now=local(2026, 12, 18, 7, 0))
    provider = FakeProvider()

    run_daily_engine(provider=provider, now=local(2026, 12, 19, 7, 0))

    assert len(provider.deliveries) == 1
    assert Dispatch.objects.get(local_date=datetime.date(2026, 12, 18)).state == "failed"
    assert Dispatch.objects.get(local_date=datetime.date(2026, 12, 19)).state == "sent"


@override_settings(DEADLINER=TEST_DEADLINER)
def test_a_retry_lists_the_registry_as_it_is_when_the_retry_is_sent() -> None:
    """Foundation section 5: the text is computed at send time from the current records, so a
    service closed between the failure and the retry is not in the retried list."""
    closed = a_service(client="Fechado", due_date=datetime.date(2026, 12, 20))
    a_service(client="Aberto", due_date=datetime.date(2026, 12, 25))
    run_daily_engine(provider=FakeProvider(accept=False), now=local(2026, 12, 18, 7, 0))
    closed.status = "completed"
    closed.save(update_fields=["status"])
    provider = FakeProvider()

    run_daily_engine(provider=provider, now=local(2026, 12, 18, 8, 0))

    assert provider.deliveries == [f"2026-12-18|1\nAberto|{SERVICE}|2026-12-25|in 7"]


@override_settings(DEADLINER=TEST_DEADLINER)
def test_the_dispatch_row_is_persisted_pending_before_the_provider_is_called() -> None:
    """Foundation section 2: the send has a persisted row before the effect fires, so a crash
    mid send leaves a visible record, never an absence."""

    class ObservingProvider:
        def __init__(self) -> None:
            self.states_at_delivery: list[str] = []

        def deliver(self, text: str) -> bool:
            self.states_at_delivery.extend(Dispatch.objects.values_list("state", flat=True))
            return True

    a_service(due_date=datetime.date(2026, 12, 25))
    provider = ObservingProvider()

    run_daily_engine(provider=provider, now=local(2026, 12, 18, 7, 0))

    assert provider.states_at_delivery == ["pending"]


@override_settings(DEADLINER=TEST_DEADLINER)
def test_the_dispatch_row_records_how_many_services_the_list_carried() -> None:
    """ADR 0002, note of 2026-11-09: the day's row carries the number of services listed."""
    a_service(client="Fazenda Boa Vista", due_date=datetime.date(2026, 12, 25))
    a_service(client="Sitio Santa Fe", due_date=datetime.date(2026, 12, 30))

    run_daily_engine(provider=FakeProvider(), now=local(2026, 12, 18, 7, 0))

    assert Dispatch.objects.get().service_count == 2


@override_settings(DEADLINER=TEST_DEADLINER)
def test_a_run_that_owes_nothing_is_silent(caplog: pytest.LogCaptureFixture) -> None:
    """ADR 0002, note of 2026-11-09: the scheduler polls every minute, so a run that owes
    nothing writes no line above debug, or sixty an hour would bury the one that sent."""
    a_service(due_date=datetime.date(2026, 12, 25))
    run_daily_engine(provider=FakeProvider(), now=local(2026, 12, 18, 7, 0))
    caplog.clear()

    with caplog.at_level(logging.INFO):
        run_daily_engine(provider=FakeProvider(), now=local(2026, 12, 18, 7, 1))

    assert [record for record in caplog.records if record.levelno >= logging.INFO] == []


@override_settings(DEADLINER=TEST_DEADLINER)
def test_a_provider_that_raises_leaves_the_days_list_failed_and_stays_loud() -> None:
    """I2: an adapter is meant to answer False, so one that raises is a defect, and it must be
    both a visible failed state and an error nobody can miss, never a row stuck pending."""

    class BrokenProvider:
        def deliver(self, text: str) -> bool:
            raise RuntimeError("the adapter is broken")

    a_service(due_date=datetime.date(2026, 12, 25))

    with pytest.raises(RuntimeError):
        run_daily_engine(provider=BrokenProvider(), now=local(2026, 12, 18, 7, 0))

    assert Dispatch.objects.get().state == "failed"
