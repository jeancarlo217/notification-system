"""B9 and B27, the scheduler: the polled command is idempotent end to end.

Traces: foundation section 5 (the scheduler lives outside the web process and, since the note of
2026-11-09 in ADR 0002, polls the command every minute), I1 (one day, one list), I3 (owed-ness
derives from persisted records, so a later poll of the same day finds nothing left to send). The
Compose scheduler service invokes exactly what this test invokes, the ``send_alerts`` command; the
provider is faked at its interface.
"""

import datetime

import pytest
from django.core.management import call_command
from django.test import override_settings

from core.models import Dispatch
from tests.builders import a_service
from tests.configuration import TEST_DEADLINER
from tests.fakes import FakeProvider

pytestmark = pytest.mark.django_db


@override_settings(DEADLINER=TEST_DEADLINER)
def test_polling_the_command_through_a_morning_delivers_one_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """I1 and I3 end to end: the scheduler polls every minute and an operator may fire the
    command by hand, and the group still receives one message that day."""
    fake = FakeProvider()
    monkeypatch.setattr("core.provider.get_provider", lambda: fake)
    a_service(due_date=datetime.date(2026, 12, 25))

    call_command("send_alerts", now="2026-12-18T06:59")
    call_command("send_alerts", now="2026-12-18T07:00")
    call_command("send_alerts", now="2026-12-18T07:01")
    call_command("send_alerts", now="2026-12-18T07:02")

    assert len(fake.deliveries) == 1
    assert Dispatch.objects.filter(state="sent").count() == 1


@override_settings(DEADLINER=TEST_DEADLINER)
def test_the_next_morning_is_a_new_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """I1 acceptance, the other side: the next day's send time owes a second message."""
    fake = FakeProvider()
    monkeypatch.setattr("core.provider.get_provider", lambda: fake)
    a_service(due_date=datetime.date(2026, 12, 25))

    call_command("send_alerts", now="2026-12-18T07:00")
    call_command("send_alerts", now="2026-12-19T06:59")
    call_command("send_alerts", now="2026-12-19T07:00")

    assert len(fake.deliveries) == 2
