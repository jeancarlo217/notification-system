"""The daily list engine (backlog B7, rewritten by B27): the decisions and the run applying them.

The decisions here are pure, plain data in and plain data out (specs/testing.md). The run at
the bottom is the effect: it reads the persisted records, sends through the provider interface
and writes the outcome back before anything depends on it (foundation section 2).
"""

import datetime
import logging
from collections.abc import Sequence
from dataclasses import dataclass

from django.db import IntegrityError, transaction

from core.models import Dispatch, Service
from core.provider import NotificationProvider
from deadliner.config import DeadlinePhrases, get_config

_logger = logging.getLogger("core.engine")

RETRY_INTERVAL = datetime.timedelta(hours=1)
"""How long a failed or unresolved attempt rests before the next one (foundation section 5)."""


@dataclass(frozen=True, slots=True)
class ServiceRecord:
    """The slice of a persisted service the list reads."""

    client: str
    service: str
    due_date: datetime.date
    status: str


@dataclass(frozen=True, slots=True)
class ListLine:
    """One open service as the message carries it."""

    client: str
    service: str
    due_date: datetime.date
    days_remaining: int


@dataclass(frozen=True, slots=True)
class DispatchRecord:
    """The slice of a day's persisted dispatch row the schedule decision reads."""

    state: str
    last_attempt_at: datetime.datetime


def list_lines(services: Sequence[ServiceRecord], today: datetime.date) -> tuple[ListLine, ...]:
    """Every active service as one line, the nearest deadline first (foundation section 4)."""
    active = (service for service in services if service.status == Service.Status.ACTIVE)
    return tuple(
        ListLine(
            client=service.client,
            service=service.service,
            due_date=service.due_date,
            days_remaining=(service.due_date - today).days,
        )
        for service in sorted(active, key=lambda service: (service.due_date, service.client))
    )


def list_is_owed(
    *,
    now: datetime.datetime,
    send_time: datetime.time,
    timezone: datetime.tzinfo,
    dispatch: DispatchRecord | None,
) -> bool:
    """Whether the day's list is owed at ``now``, given that day's dispatch record if any.

    Owed-ness derives only from the arguments, never from a clock or the database (I3).
    """
    if now.astimezone(timezone).time() < send_time:
        return False
    if dispatch is None:
        return True
    if dispatch.state == Dispatch.State.SENT:
        return False
    # Failed, or pending from a run that died: both rest an hour and are tried again (I2).
    return now - dispatch.last_attempt_at >= RETRY_INTERVAL


def deadline_phrase(days_remaining: int, phrases: DeadlinePhrases) -> str:
    """The configured phrase for a distance to the due date, chosen by its sign.

    The phrase is handed a count: the sign already chose it, so none has to print one.
    """
    if days_remaining >= 2:
        return phrases.future.format(days=days_remaining)
    if days_remaining == 1:
        return phrases.tomorrow.format(days=1)
    if days_remaining == 0:
        return phrases.today.format(days=0)
    if days_remaining == -1:
        return phrases.yesterday.format(days=1)
    return phrases.overdue.format(days=-days_remaining)


def render_list(
    lines: Sequence[ListLine],
    *,
    header: str,
    line_template: str,
    phrases: DeadlinePhrases,
    today: datetime.date,
) -> str:
    """The message text: the header, then one line per service, joined by single newlines."""
    rendered = [header.format(count=len(lines), date=today)]
    rendered.extend(
        line_template.format(
            client=line.client,
            service=line.service,
            due_date=line.due_date,
            days_remaining=line.days_remaining,
            deadline=deadline_phrase(line.days_remaining, phrases),
        )
        for line in lines
    )
    return "\n".join(rendered)


def preview_message(*, now: datetime.datetime) -> str | None:
    """The message the group would receive at ``now``, or ``None`` when nothing is open.

    It reads and renders and does nothing else: no provider, no dispatch row, no send time.
    """
    config = get_config()
    today = now.astimezone(config.timezone).date()
    lines = _open_lines(today)
    if not lines:
        return None
    return render_list(
        lines,
        header=config.message_header,
        line_template=config.message_template,
        phrases=config.deadline_phrases,
        today=today,
    )


def run_daily_engine(*, provider: NotificationProvider, now: datetime.datetime) -> None:
    """Send the day's list if it is owed at ``now``, writing the outcome back as it happens."""
    config = get_config()
    today = now.astimezone(config.timezone).date()
    dispatch = Dispatch.objects.filter(local_date=today).first()
    record = (
        None
        if dispatch is None
        else DispatchRecord(state=dispatch.state, last_attempt_at=dispatch.last_attempt_at)
    )
    if not list_is_owed(
        now=now, send_time=config.send_time, timezone=config.timezone, dispatch=record
    ):
        return

    # One read for the whole list, never one per row (foundation section 8).
    lines = _open_lines(today)
    if not lines:
        return
    text = render_list(
        lines,
        header=config.message_header,
        line_template=config.message_template,
        phrases=config.deadline_phrases,
        today=today,
    )

    # The row is pending before the send fires, so a crash mid send leaves a visible record
    # rather than an absence (foundation section 2), and a concurrent run loses here (I1).
    dispatch = _claim(dispatch, today=today, service_count=len(lines), now=now)
    if dispatch is None:
        return

    try:
        accepted = provider.deliver(text)
    except Exception:
        _settle(dispatch, Dispatch.State.FAILED, characters=len(text))
        raise
    _settle(
        dispatch,
        Dispatch.State.SENT if accepted else Dispatch.State.FAILED,
        characters=len(text),
    )


def _open_lines(today: datetime.date) -> tuple[ListLine, ...]:
    services = Service.objects.filter(status=Service.Status.ACTIVE).select_related(
        "catalog_service"
    )
    return list_lines(
        [
            ServiceRecord(
                client=service.client,
                service=service.catalog_service.name,
                due_date=service.due_date,
                status=service.status,
            )
            for service in services
        ],
        today,
    )


def _claim(
    dispatch: Dispatch | None,
    *,
    today: datetime.date,
    service_count: int,
    now: datetime.datetime,
) -> Dispatch | None:
    """The day's row, pending and stamped with this attempt, or ``None`` if another run has it."""
    if dispatch is None:
        try:
            with transaction.atomic():
                return Dispatch.objects.create(
                    local_date=today, service_count=service_count, last_attempt_at=now
                )
        except IntegrityError:
            return None

    claimed = (
        Dispatch.objects.filter(pk=dispatch.pk, last_attempt_at=dispatch.last_attempt_at)
        .exclude(state=Dispatch.State.SENT)
        .update(state=Dispatch.State.PENDING, service_count=service_count, last_attempt_at=now)
    )
    if not claimed:
        return None
    dispatch.refresh_from_db()
    return dispatch


def _settle(dispatch: Dispatch, state: str, *, characters: int) -> None:
    dispatch.state = state
    dispatch.save(update_fields=["state", "updated_at"])
    _logger.info(
        "list send",
        extra={
            "event": "list_send",
            "dispatch_id": dispatch.pk,
            "local_date": dispatch.local_date.isoformat(),
            "state": dispatch.state,
            "service_count": dispatch.service_count,
            "characters": characters,
        },
    )
