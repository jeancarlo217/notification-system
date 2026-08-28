"""The daily alert engine (backlog B7): schedule decisions and the run that applies them.

The decisions here are pure, plain data in and plain data out (specs/testing.md). The run at
the bottom is the effect: it reads the persisted records, sends through the provider interface
and writes every outcome back before anything depends on it (foundation section 2).
"""

import datetime
from collections.abc import Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass

from core.models import Alert, Service
from core.provider import NotificationProvider
from deadliner.config import get_config


@dataclass(frozen=True, slots=True)
class ServiceRecord:
    """The slice of a persisted service the schedule decision reads."""

    id: int
    due_date: datetime.date
    status: str


@dataclass(frozen=True, slots=True)
class OwedWarning:
    """One warning the catch-up rule says is owed and not yet sent."""

    service_id: int
    threshold: int


def owed_warnings(
    services: Sequence[ServiceRecord],
    thresholds: Sequence[int],
    today: datetime.date,
    sent: AbstractSet[tuple[int, int]],
) -> tuple[OwedWarning, ...]:
    """The catch-up rule of foundation section 5, as a pure decision.

    ``sent`` holds the (service id, threshold) pairs already delivered; owed-ness derives only
    from the arguments, never from a clock or the database (I3).
    """
    return tuple(
        OwedWarning(service_id=service.id, threshold=threshold)
        for service in services
        if service.status == Service.Status.ACTIVE
        for threshold in thresholds
        if service.due_date - datetime.timedelta(days=threshold) <= today
        and (service.id, threshold) not in sent
    )


def render_message(
    template: str,
    *,
    client: str,
    service: str,
    due_date: datetime.date,
    days_remaining: int,
) -> str:
    """The warning text, a pure function of the configured template and the current record."""
    return template.format(
        client=client, service=service, due_date=due_date, days_remaining=days_remaining
    )


def run_daily_engine(*, provider: NotificationProvider, today: datetime.date) -> None:
    """Send every warning owed on ``today``, writing each outcome back as it happens."""
    config = get_config()
    # Two reads for the whole run, never one per row (foundation section 8).
    services = {
        service.id: service for service in Service.objects.filter(status=Service.Status.ACTIVE)
    }
    alerts = {
        (alert.service_id, alert.threshold): alert
        for alert in Alert.objects.filter(service_id__in=services.keys())
    }
    sent = {pair for pair, alert in alerts.items() if alert.state == Alert.State.SENT}

    records = [
        ServiceRecord(id=service.id, due_date=service.due_date, status=service.status)
        for service in services.values()
    ]
    for warning in owed_warnings(records, config.alert_thresholds, today, sent):
        service = services[warning.service_id]
        pair = (warning.service_id, warning.threshold)
        # The row exists before the send fires, so a crash mid send leaves a visible record
        # rather than an absence (foundation section 2).
        alert = alerts.get(pair) or Alert.objects.create(
            service=service, threshold=warning.threshold
        )
        text = render_message(
            config.message_template,
            client=service.client,
            service=service.description,
            due_date=service.due_date,
            days_remaining=(service.due_date - today).days,
        )
        accepted = provider.deliver(text)
        alert.state = Alert.State.SENT if accepted else Alert.State.FAILED
        alert.save(update_fields=["state", "updated_at"])
