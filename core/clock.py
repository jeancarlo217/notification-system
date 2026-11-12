"""The clock as an effect (specs/testing.md): the one place the application reads the time.

Callers reach it as ``clock.now()`` through the module, never by importing the function, so a
test replaces this one attribute and every reader sees the same instant.
"""

import datetime

from deadliner.config import get_config


def now() -> datetime.datetime:
    """The current instant, on the configured clock (foundation section 5)."""
    return datetime.datetime.now(tz=get_config().timezone)
