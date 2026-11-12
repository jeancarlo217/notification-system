"""The state of the day's list and the submitter, on the screen an employee reads (B15, B27).

Traces: I2 (a send that does not succeed leaves the day's dispatch record in a failed state
visible in the interface, and no terminal state is hidden from a human), foundation section 5
(yesterday's failure stays visible after the next morning's list replaces it), ADR 0006 (the
record names who registered it), foundation section 8 (the listing reads in a constant number of
queries, whatever the dataset holds) and section 12 (the interface is in Portuguese).

The engine tests assert I2 on the rows. These read the rendered page instead, because that is
where the invariant says the failure has to be visible. The clock the screen reads is the seam
``core.clock.now``, replaced here by a fixed instant; no test reads the real time.
"""

import datetime
import re
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import replace
from typing import Any

import pytest
from django.test import Client, override_settings
from django.urls import reverse

from core.engine import run_daily_engine
from core.models import Dispatch
from core.views import SERVICES_PER_PAGE
from deadliner.config import get_config
from tests.builders import a_service, a_submitter
from tests.configuration import local
from tests.fakes import FakeProvider

pytestmark = pytest.mark.django_db

QueryCounter = Callable[..., AbstractContextManager[Any]]

DUE = datetime.date(2026, 12, 25)
TODAY = datetime.date(2026, 12, 18)
YESTERDAY = datetime.date(2026, 12, 17)
UTC = datetime.UTC
_TAG = re.compile(r"<[^>]+>")
_DISPATCH = re.compile(r'<div class="dispatch[^"]*"[^>]*>(.*?)</div>', re.DOTALL)


@pytest.fixture
def at_nine(monkeypatch: pytest.MonkeyPatch) -> None:
    """The screen is read at nine in the morning of 18 December 2026, Campo Grande time."""
    monkeypatch.setattr("core.clock.now", lambda: local(2026, 12, 18, 9, 0))


def _page(**query: str | int) -> str:
    return Client().get(reverse("service-list"), query).content.decode()


def _dispatch_notice(**query: str | int) -> str:
    """The words of the block that states what became of the day's list."""
    found = _DISPATCH.search(_page(**query))
    assert found is not None
    return " ".join(_TAG.sub(" ", found.group(1)).split())


def _cells(label: str) -> list[str]:
    """The text of every cell under ``label``, in the order the page prints the rows."""
    found = re.findall(rf'data-label="{label}">(.*?)</td>', _page(), re.DOTALL)
    return [" ".join(_TAG.sub(" ", cell).split()) for cell in found]


def _a_dispatch(day: datetime.date, state: str, hour: int = 7, minute: int = 0) -> Dispatch:
    return Dispatch.objects.create(
        local_date=day,
        state=state,
        service_count=1,
        last_attempt_at=local(day.year, day.month, day.day, hour, minute),
    )


@pytest.mark.usefixtures("at_nine")
def test_a_day_with_no_list_yet_says_so() -> None:
    """I2: the absence of a send is stated, never left to be inferred from an empty corner."""
    a_service(due_date=DUE)

    assert _dispatch_notice() == "A lista de hoje ainda não foi enviada."


@pytest.mark.usefixtures("at_nine")
def test_a_delivered_list_is_shown_as_sent_with_the_time_it_went() -> None:
    """B27, the interface: sent, and when."""
    a_service(due_date=DUE)
    _a_dispatch(TODAY, "sent", 7, 0)

    assert _dispatch_notice() == "Lista de hoje enviada às 07:00."


@pytest.mark.usefixtures("at_nine")
def test_a_rejected_send_is_shown_as_failed_with_the_time_of_the_next_attempt() -> None:
    """I2 acceptance: with the provider rejecting, the interface shows the day's list as failed,
    and says when it is tried again."""
    a_service(due_date=DUE)
    # The real configuration with only the send time pinned: `deadliner/urls.py` reads the path
    # segment once at import, so this file never overrides it.
    seven = replace(get_config(), send_time=datetime.time(7, 0))

    with override_settings(DEADLINER=seven):
        run_daily_engine(provider=FakeProvider(accept=False), now=local(2026, 12, 18, 8, 30))

    assert _dispatch_notice() == (
        "O envio da lista de hoje falhou às 08:30. Nova tentativa às 09:30."
    )


@pytest.mark.usefixtures("at_nine")
def test_a_send_that_started_and_reported_nothing_is_shown_as_unconfirmed() -> None:
    """I2: no state is invisible, so a row left mid attempt is named on the screen with the time
    the engine takes it up again."""
    a_service(due_date=DUE)
    _a_dispatch(TODAY, "pending", 8, 30)

    assert _dispatch_notice() == (
        "O envio da lista de hoje começou às 08:30 e não foi confirmado. Nova tentativa às 09:30."
    )


@pytest.mark.usefixtures("at_nine")
def test_the_times_on_screen_are_on_the_configured_clock() -> None:
    """Foundation section 5: an attempt stored at 11:00 UTC happened at seven in Campo Grande."""
    a_service(due_date=DUE)
    Dispatch.objects.create(
        local_date=TODAY,
        state="sent",
        service_count=1,
        last_attempt_at=datetime.datetime(2026, 12, 18, 11, 0, tzinfo=UTC),
    )

    assert _dispatch_notice() == "Lista de hoje enviada às 07:00."


@pytest.mark.usefixtures("at_nine")
def test_yesterdays_failure_stays_on_screen_until_a_later_list_is_sent() -> None:
    """I2, foundation section 5: the next morning's list replaces yesterday's, and yesterday's
    failure stays visible until one is delivered."""
    a_service(due_date=DUE)
    _a_dispatch(YESTERDAY, "failed", 23, 0)

    assert _dispatch_notice() == (
        "A lista de hoje ainda não foi enviada. A lista de 17/12/2026 não foi entregue."
    )


@pytest.mark.usefixtures("at_nine")
def test_yesterdays_failure_leaves_the_screen_once_todays_list_is_sent() -> None:
    """I2, the quiet side: a failure a later list has answered is no longer what a person acts
    on."""
    a_service(due_date=DUE)
    _a_dispatch(YESTERDAY, "failed", 23, 0)
    _a_dispatch(TODAY, "sent", 7, 0)

    assert _dispatch_notice() == "Lista de hoje enviada às 07:00."


@pytest.mark.usefixtures("at_nine")
def test_a_delivered_list_from_yesterday_is_not_reported_as_a_failure() -> None:
    """I2, the quiet side: only an undelivered list is named, never every earlier day."""
    a_service(due_date=DUE)
    _a_dispatch(YESTERDAY, "sent", 7, 0)

    assert _dispatch_notice() == "A lista de hoje ainda não foi enviada."


@pytest.mark.usefixtures("at_nine")
def test_the_failed_state_is_marked_for_the_layout_and_said_in_words() -> None:
    """B15, kept by B27: a red block is unreadable to a reader who cannot see it, so the state
    is a sentence and the class only decides how it is drawn."""
    a_service(due_date=DUE)
    _a_dispatch(TODAY, "failed", 7, 0)

    page = _page()

    assert 'class="dispatch dispatch--failed"' in page
    assert "falhou" in _dispatch_notice()


@pytest.mark.usefixtures("at_nine")
def test_the_state_of_the_days_list_is_shown_while_searching_too() -> None:
    """I2: a failure does not hide behind a search that happens to find nothing."""
    a_service(due_date=DUE)
    _a_dispatch(TODAY, "failed", 7, 0)

    assert "falhou às 07:00" in _dispatch_notice(q="nenhum cliente com este nome")


def test_the_list_names_who_registered_each_record() -> None:
    """ADR 0006: the column that decision promised, answering who entered this record."""
    a_service(client="Fazenda Boa Vista", submitter=a_submitter("Geovanna"))

    assert _cells("Responsável") == ["Geovanna"]


def test_the_list_no_longer_carries_a_column_of_warnings() -> None:
    """B27: the thresholds stopped existing, so nothing on the screen is counted per threshold."""
    a_service(due_date=DUE)

    page = _page()

    assert "Responsável" in page
    assert 'data-label="Responsável"' in page
    assert "Avisos" not in page


@pytest.mark.usefixtures("at_nine")
def test_the_state_of_the_days_list_and_the_submitter_cost_no_query_per_row(
    django_assert_max_num_queries: QueryCounter,
    django_assert_num_queries: QueryCounter,
) -> None:
    """Foundation section 8: the listing reads a constant number of queries, whatever it holds."""
    _a_dispatch(YESTERDAY, "failed", 23, 0)
    _a_dispatch(TODAY, "failed", 7, 0)
    a_service(client="Cliente 000", due_date=DUE)
    browser = Client()

    with django_assert_max_num_queries(5) as one_record:
        browser.get(reverse("service-list"))

    for number in range(1, SERVICES_PER_PAGE + 5):
        a_service(client=f"Cliente {number:03d}", due_date=DUE + datetime.timedelta(days=number))

    with django_assert_num_queries(len(one_record.captured_queries)):
        browser.get(reverse("service-list"))
