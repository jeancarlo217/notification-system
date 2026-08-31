"""B7, the daily engine run: effects against the database through the provider interface.

Traces: foundation section 2 (truth lives in persisted records, outcomes written back), section
5 (the catch-up rule at the effect layer), I1 (run twice, one delivery per warning), I2 (a
rejected send is a visible failed state, retried next run), I3 (a run after missed days sends
every never-sent warning once). The provider is faked at its interface, the clock is the
``today`` argument; no network, no real time (specs/testing.md).
"""

import datetime
from zoneinfo import ZoneInfo

import pytest
from django.test import override_settings

from core.engine import run_daily_engine
from core.models import Alert, Service
from deadliner.config import DeadlinerConfig
from tests.builders import DEFAULT_CATALOG_SERVICE, a_service
from tests.fakes import FakeProvider

pytestmark = pytest.mark.django_db

TEST_DEADLINER = DeadlinerConfig(
    alert_thresholds=(30, 7, 0),
    whatsapp_number="5567999998888",
    message_template="{client}|{service}|{due_date}|{days_remaining}",
    secret_path_segment="fake-segment-for-tests",
    timezone=ZoneInfo("America/Campo_Grande"),
)


def _a_service(
    due: datetime.date,
    status: str = "active",
    client: str = "Fazenda Boa Vista",
) -> Service:
    return a_service(client=client, due_date=due, status=status)


@override_settings(DEADLINER=TEST_DEADLINER)
def test_running_the_engine_twice_delivers_each_owed_warning_once() -> None:
    """I1 acceptance: run twice on the same day; one delivery per owed warning, ever."""
    _a_service(due=datetime.date(2026, 12, 25))
    provider = FakeProvider()

    run_daily_engine(provider=provider, today=datetime.date(2026, 12, 18))
    run_daily_engine(provider=provider, today=datetime.date(2026, 12, 18))

    assert len(provider.deliveries) == 2
    assert Alert.objects.filter(state="sent").count() == 2


@override_settings(DEADLINER=TEST_DEADLINER)
def test_a_run_after_missed_days_sends_each_passed_warning_exactly_once() -> None:
    """I3 acceptance: two trigger dates passed with no runs; one run sends both, once each."""
    service = _a_service(due=datetime.date(2026, 12, 25))
    provider = FakeProvider()

    run_daily_engine(provider=provider, today=datetime.date(2026, 12, 20))

    assert len(provider.deliveries) == 2
    sent_thresholds = set(
        Alert.objects.filter(service=service, state="sent").values_list("threshold", flat=True)
    )
    assert sent_thresholds == {30, 7}


@override_settings(DEADLINER=TEST_DEADLINER)
def test_a_rejected_send_is_a_visible_failed_state_retried_next_run() -> None:
    """I2 acceptance: rejection persists as failed; the next run attempts the same alert."""
    service = _a_service(due=datetime.date(2027, 1, 17))
    rejecting = FakeProvider(accept=False)

    run_daily_engine(provider=rejecting, today=datetime.date(2026, 12, 18))

    failed = Alert.objects.get(service=service, threshold=30)
    assert failed.state == "failed"

    accepting = FakeProvider()
    run_daily_engine(provider=accepting, today=datetime.date(2026, 12, 19))

    assert len(accepting.deliveries) == 1
    retried = Alert.objects.get(service=service, threshold=30)
    assert retried.state == "sent"
    assert Alert.objects.filter(service=service, threshold=30).count() == 1


@override_settings(DEADLINER=TEST_DEADLINER)
def test_the_message_is_computed_at_send_time_from_the_current_record() -> None:
    """Foundation section 5: a late catch-up message carries today's distance to the due date,
    never the threshold it implements."""
    _a_service(due=datetime.date(2026, 12, 25))
    provider = FakeProvider()

    run_daily_engine(provider=provider, today=datetime.date(2026, 12, 15))

    assert provider.deliveries == [f"Fazenda Boa Vista|{DEFAULT_CATALOG_SERVICE}|2026-12-25|10"]


@override_settings(DEADLINER=TEST_DEADLINER)
def test_a_completed_service_is_never_messaged() -> None:
    """Foundation section 3: warnings are computed only for active services."""
    _a_service(due=datetime.date(2026, 12, 18), status="completed")
    provider = FakeProvider()

    run_daily_engine(provider=provider, today=datetime.date(2026, 12, 18))

    assert provider.deliveries == []
    assert Alert.objects.count() == 0


@override_settings(DEADLINER=TEST_DEADLINER)
def test_the_alert_row_is_persisted_before_the_provider_is_called() -> None:
    """Foundation section 2: the send has a persisted row before the effect fires, so a crash
    mid send leaves a visible record, never an absence."""

    class ObservingProvider:
        def __init__(self) -> None:
            self.rows_at_delivery: list[int] = []

        def deliver(self, text: str) -> bool:
            self.rows_at_delivery.append(Alert.objects.count())
            return True

    _a_service(due=datetime.date(2027, 1, 17))
    provider = ObservingProvider()

    run_daily_engine(provider=provider, today=datetime.date(2026, 12, 18))

    assert provider.rows_at_delivery == [1]


@override_settings(DEADLINER=TEST_DEADLINER)
def test_a_pending_alert_left_by_a_crash_is_attempted_and_not_duplicated() -> None:
    """Foundation section 2 and I1: a pending row from an interrupted run is owed and not sent;
    the next run delivers it once through the same row."""
    service = _a_service(due=datetime.date(2027, 1, 17))
    Alert.objects.create(service=service, threshold=30)
    provider = FakeProvider()

    run_daily_engine(provider=provider, today=datetime.date(2026, 12, 18))

    assert len(provider.deliveries) == 1
    assert Alert.objects.filter(service=service, threshold=30).count() == 1
    assert Alert.objects.get(service=service, threshold=30).state == "sent"
