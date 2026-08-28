"""The daily engine as a management command (backlog B7, foundation section 5)."""

import argparse
import datetime
from typing import Any

from django.core.management.base import BaseCommand

from core import provider
from core.engine import run_daily_engine
from deadliner.config import get_config


class Command(BaseCommand):
    help = "Send every warning owed today (foundation section 5)."

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--today",
            help="ISO date to run as, instead of today in the configured time zone.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        run_daily_engine(provider=provider.get_provider(), today=_today(options["today"]))


def _today(raw: str | None) -> datetime.date:
    if raw is not None:
        return datetime.date.fromisoformat(raw)
    return datetime.datetime.now(tz=get_config().timezone).date()
