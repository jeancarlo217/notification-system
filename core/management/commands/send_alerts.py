"""The daily engine as a management command (backlog B7 and B27, foundation section 5)."""

import argparse
import datetime
import uuid
from typing import Any

from django.core.management.base import BaseCommand

from core import clock, provider
from core.engine import preview_message, run_daily_engine
from deadliner.config import get_config
from deadliner.log_context import bind_log_context, reset_log_context


class _ProviderResolvedOnDelivery:
    """The configured provider, looked up only when a list is actually sent.

    The scheduler polls every minute (ADR 0002), and a run that owes nothing must not fail on a
    provider it never needed.
    """

    def deliver(self, text: str) -> bool:
        return provider.get_provider().deliver(text)


class Command(BaseCommand):
    help = "Send the day's list of open services if it is owed now (foundation section 5)."

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--now",
            help=(
                "ISO date and time to run as, instead of the current instant. With no offset "
                "it is read on the configured clock, for example 2026-12-18T07:00."
            ),
        )
        parser.add_argument(
            "--preview",
            action="store_true",
            help=(
                "Print the message the group would receive and send nothing: no provider is "
                "called, no dispatch row is written and the send time is ignored."
            ),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        now = _now(options["now"])
        if options["preview"]:
            self._preview(now)
            return
        # The run binds its correlation key once, like a request does (foundation section 8).
        token = bind_log_context(run_id=uuid.uuid4().hex)
        try:
            run_daily_engine(provider=_ProviderResolvedOnDelivery(), now=now)
        finally:
            reset_log_context(token)

    def _preview(self, now: datetime.datetime) -> None:
        text = preview_message(now=now)
        if text is None:
            self.stderr.write("No active service: no message would be sent.")
            return
        self.stdout.write(text)
        self.stderr.write(f"{len(text)} characters.")


def _now(raw: str | None) -> datetime.datetime:
    if raw is None:
        return clock.now()
    given = datetime.datetime.fromisoformat(raw)
    if given.tzinfo is None:
        return given.replace(tzinfo=get_config().timezone)
    return given
