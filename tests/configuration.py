"""The business configuration the tests run under, so one new variable edits one file.

The wording here is deliberately not the owner's: a test that is about the engine reads a message
made of pipes and English words, so a change to the approved Portuguese of foundation section 4
never breaks a test that was not about wording. The tests that are about the wording spell the
approved text out themselves.
"""

import datetime
from dataclasses import replace
from typing import Any
from zoneinfo import ZoneInfo

from deadliner.config import DeadlinePhrases, DeadlinerConfig

CAMPO_GRANDE = ZoneInfo("America/Campo_Grande")

TEST_PHRASES = DeadlinePhrases(
    future="in {days}",
    tomorrow="tomorrow",
    today="today",
    yesterday="yesterday",
    overdue="{days} ago",
)

TEST_DEADLINER = DeadlinerConfig(
    send_time=datetime.time(7, 0),
    whatsapp_destination="5567999998888",
    message_header="{date}|{count}",
    message_template="{client}|{service}|{due_date}|{deadline}",
    deadline_phrases=TEST_PHRASES,
    secret_path_segment="fake-segment-for-tests",
    timezone=CAMPO_GRANDE,
)


def a_deadliner_config(**overrides: Any) -> DeadlinerConfig:
    """``TEST_DEADLINER`` with the named values replaced."""
    return replace(TEST_DEADLINER, **overrides)


def local(year: int, month: int, day: int, hour: int = 7, minute: int = 0) -> datetime.datetime:
    """An instant on the wall clock of America/Campo_Grande, which is what the engine is handed."""
    return datetime.datetime(year, month, day, hour, minute, tzinfo=CAMPO_GRANDE)
