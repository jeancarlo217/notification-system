"""B27, the daily management command: the thin shell that injects the clock and the provider.

Traces: foundation section 5 (the engine is a management command the scheduler polls), I3 (the
clock is injected, here as the ``--now`` argument, read in the configured zone), I5 (the preview
mode is how the real message is read where the real records live), ADR 0002 note of 2026-11-09
(a run that owes nothing does nothing), and rule 3 of the parallel plan in ``specs/backlog.md``:
the command resolves its provider through ``core.provider.get_provider`` at call time, which is
the seam where B8 plugs the Evolution adapter in.
"""

import datetime
from io import StringIO

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.test import override_settings

from core.models import Dispatch
from tests.builders import a_service
from tests.configuration import TEST_DEADLINER
from tests.fakes import FakeProvider

pytestmark = pytest.mark.django_db

SERVICE = "Licenciamentos Ambientais"


def _no_provider() -> FakeProvider:
    raise ImproperlyConfigured("no provider may be resolved in this test")


@override_settings(DEADLINER=TEST_DEADLINER)
def test_the_command_sends_the_list_owed_at_the_given_instant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Foundation section 5: the command is the engine with the clock and provider injected."""
    fake = FakeProvider()
    monkeypatch.setattr("core.provider.get_provider", lambda: fake)
    a_service(due_date=datetime.date(2026, 12, 25))

    call_command("send_alerts", now="2026-12-18T07:00")

    assert fake.deliveries == [f"2026-12-18|1\nFazenda Boa Vista|{SERVICE}|2026-12-25|in 7"]


@override_settings(DEADLINER=TEST_DEADLINER)
def test_the_given_instant_is_read_on_the_configured_clock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B27 rule 4: `--now` with no offset is wall time in the configured zone, so 06:59 is before
    the send time whatever zone the host is in."""
    fake = FakeProvider()
    monkeypatch.setattr("core.provider.get_provider", lambda: fake)
    a_service(due_date=datetime.date(2026, 12, 25))

    call_command("send_alerts", now="2026-12-18T06:59")

    assert fake.deliveries == []


@override_settings(DEADLINER=TEST_DEADLINER)
def test_a_run_that_owes_nothing_never_asks_for_a_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ADR 0002, note of 2026-11-09: the scheduler polls every minute, so a run before the send
    time must exit quietly even where no provider can be resolved."""
    monkeypatch.setattr("core.provider.get_provider", _no_provider)
    a_service(due_date=datetime.date(2026, 12, 25))

    call_command("send_alerts", now="2026-12-18T06:59")

    assert Dispatch.objects.count() == 0


def test_the_provider_factory_refuses_while_the_adapter_is_missing() -> None:
    """I2: with no adapter delivered yet (B8), resolving the provider fails loudly, never as a
    silent no-op."""
    from core.provider import get_provider

    with pytest.raises(ImproperlyConfigured):
        get_provider()


@override_settings(DEADLINER=TEST_DEADLINER)
def test_the_preview_prints_the_message_and_sends_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B27, the preview mode: the text the group would receive, with no provider touched and no
    dispatch row written."""
    monkeypatch.setattr("core.provider.get_provider", _no_provider)
    a_service(due_date=datetime.date(2026, 12, 25))
    printed = StringIO()

    call_command("send_alerts", preview=True, now="2026-12-18T07:00", stdout=printed)

    assert printed.getvalue() == f"2026-12-18|1\nFazenda Boa Vista|{SERVICE}|2026-12-25|in 7\n"
    assert Dispatch.objects.count() == 0


@override_settings(DEADLINER=TEST_DEADLINER)
def test_the_preview_ignores_the_send_time(monkeypatch: pytest.MonkeyPatch) -> None:
    """B27, the preview mode: it answers what the message is, not whether it is owed, so it
    prints at three in the morning too."""
    monkeypatch.setattr("core.provider.get_provider", _no_provider)
    a_service(due_date=datetime.date(2026, 12, 25))
    printed = StringIO()

    call_command("send_alerts", preview=True, now="2026-12-18T03:00", stdout=printed)

    assert printed.getvalue() == f"2026-12-18|1\nFazenda Boa Vista|{SERVICE}|2026-12-25|in 7\n"


@override_settings(DEADLINER=TEST_DEADLINER)
def test_the_preview_is_safe_to_run_twice_and_leaves_the_days_list_owed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B27, the preview mode, and I1: previewing consumes nothing, so the real run of the same
    day still sends its one list."""
    a_service(due_date=datetime.date(2026, 12, 25))
    call_command("send_alerts", preview=True, now="2026-12-18T07:00", stdout=StringIO())
    call_command("send_alerts", preview=True, now="2026-12-18T07:00", stdout=StringIO())
    fake = FakeProvider()
    monkeypatch.setattr("core.provider.get_provider", lambda: fake)

    call_command("send_alerts", now="2026-12-18T07:00")

    assert len(fake.deliveries) == 1


@override_settings(DEADLINER=TEST_DEADLINER)
def test_the_preview_of_an_empty_registry_prints_no_message() -> None:
    """B27 rule 3 through the preview: no active service means there is no message to show."""
    a_service(due_date=datetime.date(2026, 12, 25), status="completed")
    printed = StringIO()

    call_command("send_alerts", preview=True, now="2026-12-18T07:00", stdout=printed)

    assert printed.getvalue() == ""
