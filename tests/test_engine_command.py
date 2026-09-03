"""B7, the daily management command: the thin shell that injects the clock and the provider.

Traces: foundation section 5 (the engine is a management command run once a day), I3 (the clock
is injected, here as the ``--today`` argument), and rule 3 of the parallel plan in
``specs/backlog.md``: the command resolves its provider through ``core.provider.get_provider``
at call time, which is the seam where B8 plugs the Evolution adapter in.
"""

import datetime
from zoneinfo import ZoneInfo

import pytest
from django.core.management import call_command
from django.test import override_settings

from deadliner.config import DeadlinerConfig
from tests.builders import a_service
from tests.fakes import FakeProvider

pytestmark = pytest.mark.django_db

TEST_DEADLINER = DeadlinerConfig(
    alert_thresholds=(30, 7, 0),
    whatsapp_destination="5567999998888",
    message_template="{client}|{service}|{due_date}|{days_remaining}",
    secret_path_segment="fake-segment-for-tests",
    timezone=ZoneInfo("America/Campo_Grande"),
)


@override_settings(DEADLINER=TEST_DEADLINER)
def test_the_command_runs_the_engine_for_the_given_day(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Foundation section 5: the command is the engine with the clock and provider injected."""
    fake = FakeProvider()
    monkeypatch.setattr("core.provider.get_provider", lambda: fake)
    a_service(due_date=datetime.date(2026, 12, 25))

    call_command("send_alerts", today="2026-12-18")

    assert len(fake.deliveries) == 2


def test_the_provider_factory_refuses_while_the_adapter_is_missing() -> None:
    """I2 and OQ-1: with no adapter delivered yet (B8), resolving the provider fails loudly,
    never as a silent no-op."""
    from django.core.exceptions import ImproperlyConfigured

    from core.provider import get_provider

    with pytest.raises(ImproperlyConfigured):
        get_provider()
