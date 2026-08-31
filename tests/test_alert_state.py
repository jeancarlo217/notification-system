"""Alert state and the submitter, on the screen an employee reads (backlog B15).

Traces: I2 (a send that does not succeed leaves a failed state visible in the interface, and no
terminal state is hidden from a human), I4 (the thresholds the screen prints come from
configuration, never from three columns written into the template), ADR 0006 (the record names who
registered it), foundation section 8 (the listing reads in a constant number of queries, whatever
the dataset holds) and section 12 (the interface is in Portuguese).

B7 satisfied I2 at the persisted-state layer only, which ``tests/test_engine_run.py`` asserts on
the rows. These tests read the rendered page instead, because that is where the invariant says the
failure has to be visible.
"""

import datetime
import re
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from dataclasses import replace
from typing import Any

import pytest
from django.test import Client, override_settings
from django.urls import reverse

from core.engine import run_daily_engine
from core.models import Alert
from core.views import SERVICES_PER_PAGE
from deadliner.config import DeadlinerConfig, get_config
from tests.builders import a_service, a_submitter
from tests.fakes import FakeProvider

pytestmark = pytest.mark.django_db

QueryCounter = Callable[..., AbstractContextManager[Any]]

DEFAULT_THRESHOLDS = (30, 7, 0)
OTHER_THRESHOLDS = (45, 1)
DUE = datetime.date(2026, 12, 25)
_TAG = re.compile(r"<[^>]+>")


def _configured(*thresholds: int) -> DeadlinerConfig:
    """The real configuration with only the thresholds replaced (I4).

    The path segment is copied rather than faked on purpose: ``deadliner/urls.py`` reads it once
    at import, so overriding it while a URL is being resolved freezes a segment that never
    existed into every ``reverse`` the suite makes afterwards.
    """
    return replace(get_config(), alert_thresholds=thresholds)


@pytest.fixture
def default_thresholds() -> Iterator[None]:
    """The 30, 7 and 0 day warnings of foundation section 5, whatever the environment configures."""
    with override_settings(DEADLINER=_configured(*DEFAULT_THRESHOLDS)):
        yield


def _cells(label: str, **query: str | int) -> list[str]:
    """The text of every cell under ``label``, in the order the page prints the rows."""
    page = Client().get(reverse("service-list"), query).content.decode()
    found = re.findall(rf'data-label="{label}">(.*?)</td>', page, re.DOTALL)
    return [" ".join(_TAG.sub(" ", cell).split()) for cell in found]


def _page(**query: str | int) -> str:
    return Client().get(reverse("service-list"), query).content.decode()


@pytest.mark.usefixtures("default_thresholds")
def test_a_delivered_warning_is_listed_as_sent() -> None:
    """I2: what became of a warning is answered on the screen, not only in the table."""
    service = a_service(due_date=DUE)
    Alert.objects.create(service=service, threshold=30, state=Alert.State.SENT)

    assert "30d enviado" in _cells("Avisos")[0]


@pytest.mark.usefixtures("default_thresholds")
def test_a_rejected_send_is_listed_as_failed() -> None:
    """I2 acceptance, the half B7 left open: with the provider rejecting, the interface says so."""
    a_service(due_date=DUE)

    run_daily_engine(provider=FakeProvider(accept=False), today=datetime.date(2026, 12, 20))

    assert "7d falhou" in _cells("Avisos")[0]


@pytest.mark.usefixtures("default_thresholds")
def test_a_threshold_with_no_alert_row_is_listed_as_waiting_and_never_as_failed() -> None:
    """I2: a warning whose date has not arrived has not failed, and the screen must not say it."""
    a_service(due_date=DUE)

    cell = _cells("Avisos")[0]

    assert cell == "30d aguardando 7d aguardando 0d aguardando"


@pytest.mark.usefixtures("default_thresholds")
def test_a_send_that_started_and_reported_nothing_is_listed_as_pending() -> None:
    """I2: no terminal state is invisible, so a row left mid attempt is named on the screen."""
    service = a_service(due_date=DUE)
    Alert.objects.create(service=service, threshold=7)

    assert "7d pendente" in _cells("Avisos")[0]


def test_the_listed_warnings_follow_the_configured_thresholds() -> None:
    """I4 acceptance: two threshold configurations, two sets of warnings, no code change."""
    a_service(due_date=DUE)

    with override_settings(DEADLINER=_configured(*DEFAULT_THRESHOLDS)):
        default = _cells("Avisos")[0]
    with override_settings(DEADLINER=_configured(*OTHER_THRESHOLDS)):
        other = _cells("Avisos")[0]

    assert default == "30d aguardando 7d aguardando 0d aguardando"
    assert other == "45d aguardando 1d aguardando"


@pytest.mark.usefixtures("default_thresholds")
def test_each_warning_states_its_condition_in_words_and_never_by_colour_alone() -> None:
    """B15: a red dot is unreadable to a reader who cannot see it, so every state is a word."""
    service = a_service(due_date=DUE)
    Alert.objects.create(service=service, threshold=30, state=Alert.State.SENT)
    Alert.objects.create(service=service, threshold=7, state=Alert.State.FAILED)

    assert _cells("Avisos")[0] == "30d enviado 7d falhou 0d aguardando"


def test_the_list_names_who_registered_each_record() -> None:
    """ADR 0006: the column that decision promised, answering who entered this record."""
    a_service(client="Fazenda Boa Vista", submitter=a_submitter("Geovanna"))

    assert _cells("Responsável") == ["Geovanna"]


def test_the_list_names_its_two_new_columns_in_portuguese() -> None:
    """Foundation section 12: the dataset the company works from is labelled in its language."""
    a_service(due_date=DUE)

    page = _page()

    for heading in ("Responsável", "Avisos"):
        assert heading in page


def test_the_two_new_cells_carry_their_column_name_for_the_block_layout() -> None:
    """B14: below 40rem the table is laid out as blocks, so each cell prints its own column name."""
    a_service(due_date=DUE)

    page = _page()

    assert 'data-label="Responsável"' in page
    assert 'data-label="Avisos"' in page


@pytest.mark.usefixtures("default_thresholds")
def test_the_warnings_and_the_submitter_cost_no_query_per_row(
    django_assert_max_num_queries: QueryCounter,
    django_assert_num_queries: QueryCounter,
) -> None:
    """Foundation section 8: the listing reads a constant number of queries, whatever it holds."""
    _services_with_every_warning(1)
    browser = Client()

    with django_assert_max_num_queries(5) as one_record:
        browser.get(reverse("service-list"))

    _services_with_every_warning(SERVICES_PER_PAGE + 5)

    with django_assert_num_queries(len(one_record.captured_queries)):
        browser.get(reverse("service-list"))


def _services_with_every_warning(count: int) -> None:
    """``count`` records, each carrying one alert row per configured threshold."""
    for number in range(count):
        service = a_service(
            client=f"Cliente {number:03d}", due_date=DUE + datetime.timedelta(days=number)
        )
        for threshold in DEFAULT_THRESHOLDS:
            Alert.objects.create(service=service, threshold=threshold, state=Alert.State.SENT)
