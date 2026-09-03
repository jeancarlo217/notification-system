"""B9, the scheduler: the daily command is idempotent end to end.

Traces: foundation section 5 (one daily run by a scheduler that lives outside the web process),
I1 (run twice, one delivery per warning), I3 (owed-ness derives from persisted records, so a
second run on the same day finds nothing left to send). The Compose scheduler service invokes
exactly what this test invokes, the ``send_alerts`` command; the provider is faked at its
interface, since OQ-1 keeps the real adapter out until B8.
"""

import datetime
from zoneinfo import ZoneInfo

import pytest
from django.core.management import call_command
from django.test import override_settings

from core.models import Alert
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
def test_running_the_command_twice_delivers_each_owed_warning_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """I1 and I3 end to end: the scheduler and an operator can both fire the command on the
    same day and the company phone still receives one message per owed warning."""
    fake = FakeProvider()
    monkeypatch.setattr("core.provider.get_provider", lambda: fake)
    a_service(due_date=datetime.date(2026, 12, 25))

    call_command("send_alerts", today="2026-12-18")
    call_command("send_alerts", today="2026-12-18")

    assert len(fake.deliveries) == 2
    assert Alert.objects.filter(state="sent").count() == 2
