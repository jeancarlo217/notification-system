"""The CSV export an employee downloads (backlog B10).

Traces: foundation section 7 (a CSV export button in version 1, producing one row per service
record with every business field, as a single streamed query), section 8 (the export reads the
database in a constant number of queries, never one per row), section 6 (the route lives under the
configured path segment like everything but the health endpoint), ADR 0005 and ADR 0006 (the two
references resolve to columns on the way out), I4 (the time zone the file is dated in is
configuration) and section 12 (the file the company opens is in Portuguese).

The export is the whole dataset. B17's search and pages are a way to read the list on a screen,
never a filter on what the company owns, so a narrowed screen still exports every record.
"""

import codecs
import datetime
import re
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from dataclasses import replace
from typing import Any, cast
from zoneinfo import ZoneInfo

import pytest
from django.http import StreamingHttpResponse
from django.test import Client, override_settings
from django.urls import reverse

from core.export import EXPORT_HEADER, csv_line
from core.models import Service
from core.views import SERVICES_PER_PAGE
from deadliner.config import DeadlinerConfig, get_config
from tests.builders import a_catalog_service, a_service, a_submitter

pytestmark = pytest.mark.django_db

QueryCounter = Callable[..., AbstractContextManager[Any]]

# Two zones twenty six hours apart, so the day they are on always differs whatever the moment.
FURTHEST_EAST = ZoneInfo("Pacific/Kiritimati")
FURTHEST_WEST = ZoneInfo("Etc/GMT+12")

_FILENAME = re.compile(r'filename="(?P<name>[^"]+)"')


def _configured(timezone: ZoneInfo) -> DeadlinerConfig:
    """The real configuration with only the time zone replaced (I4).

    The path segment is copied rather than faked on purpose: ``deadliner/urls.py`` reads it once
    at import, so overriding it while a URL is being resolved freezes a segment that never
    existed into every ``reverse`` the suite makes afterwards.
    """
    return replace(get_config(), timezone=timezone)


def _export_response(browser: Client, /, **query: str | int) -> StreamingHttpResponse:
    """The export, typed as the streaming response it is.

    The test client stub types every response as the buffered one, which is what makes both casts
    in this file necessary rather than decorative.
    """
    return cast(StreamingHttpResponse, browser.get(reverse("service-export"), query))


def _joined(response: StreamingHttpResponse) -> bytes:
    """The streamed chunks as the one file they make."""
    return b"".join(cast(Iterator[bytes], response.streaming_content))


def _body(**query: str | int) -> bytes:
    """The exported file exactly as it reaches the browser, byte order mark included."""
    return _joined(_export_response(Client(), **query))


def _download(**query: str | int) -> str:
    """The exported file as text, with the byte order mark consumed as a reader consumes it."""
    return _body(**query).decode("utf-8-sig")


def _rows(**query: str | int) -> list[str]:
    """The data lines of the exported file, the header dropped."""
    return _download(**query).splitlines()[1:]


def _clients_in(text: str) -> list[str]:
    """The client of every data line, in the order the file prints them."""
    return [line.split(";")[0] for line in text.splitlines()[1:]]


def _services_named(count: int) -> None:
    """``count`` records, each due a day later than the one before, so the order is unambiguous."""
    for number in range(count):
        a_service(
            client=f"Cliente {number:03d}",
            due_date=datetime.date(2027, 1, 1) + datetime.timedelta(days=number),
        )


def test_the_export_answers_one_row_per_service_record() -> None:
    """Foundation section 7: one row per service record, under one header line."""
    _services_named(3)

    text = _download()

    assert text.splitlines()[0] == csv_line(EXPORT_HEADER).rstrip("\r\n")
    assert len(_rows()) == 3


def test_the_exported_row_carries_the_catalogue_and_the_submitter_as_columns() -> None:
    """ADR 0005 and ADR 0006: a reference resolves to one column on the way out, so the flatness
    promise of foundation section 3 survives the two foreign keys."""
    a_service(
        client="Fazenda Boa Vista",
        catalog_service=a_catalog_service("Georreferenciamento", category="Geotecnologias"),
        notes="Renovação anual",
        start_date=datetime.date(2026, 9, 5),
        term_days=20,
        submitter=a_submitter("Geovanna"),
    )

    row = _rows()[0]

    assert row == "Fazenda Boa Vista;Geotecnologias;Georreferenciamento;Renovação anual;" + (
        f"05/09/2026;20;25/09/2026;Ativo;Geovanna;{_created_cell()}"
    )


def _created_cell() -> str:
    """What the one record in the database reports as the moment it was created."""
    created = Service.objects.get().created_at.astimezone(get_config().timezone)
    return created.strftime("%d/%m/%Y %H:%M")


def test_a_completed_record_is_exported_beside_the_active_ones() -> None:
    """Foundation section 3: status is the whole lifecycle, so the file carries both states."""
    a_service(client="Ativo SA", due_date=datetime.date(2027, 1, 1))
    a_service(client="Concluído SA", due_date=datetime.date(2027, 1, 2), status="completed")

    text = _download()

    assert _clients_in(text) == ["Ativo SA", "Concluído SA"]
    assert ";Concluído;" in text


def test_the_export_carries_the_whole_dataset_and_never_one_page_of_it() -> None:
    """Foundation section 7: one row per service record. B17's pages are a way to read the list
    on a screen, never a statement about what the company owns."""
    _services_named(SERVICES_PER_PAGE + 5)

    assert len(_rows()) == SERVICES_PER_PAGE + 5


def test_the_export_carries_the_whole_dataset_and_never_the_current_search() -> None:
    """Foundation section 7: a narrowed screen still exports every record the company owns."""
    a_service(client="Fazenda Boa Vista", due_date=datetime.date(2027, 1, 1))
    a_service(client="Sítio das Palmeiras", due_date=datetime.date(2027, 1, 2))

    assert _clients_in(_download(q="Fazenda")) == ["Fazenda Boa Vista", "Sítio das Palmeiras"]


def test_the_file_follows_the_deadline_order_the_list_shows() -> None:
    """B10: the file and the screen answer in one order, so the two never disagree on a row."""
    a_service(client="Depois SA", due_date=datetime.date(2027, 3, 1))
    a_service(client="Antes SA", due_date=datetime.date(2027, 1, 1))

    assert _clients_in(_download()) == ["Antes SA", "Depois SA"]


def test_the_file_opens_with_the_byte_order_mark_a_spreadsheet_reads() -> None:
    """B10: without it Excel reads the file in the system code page and every accented client
    name arrives as mojibake."""
    a_service(client="José Victor Participações")

    body = _body()

    assert body.startswith(codecs.BOM_UTF8)
    assert "José Victor Participações".encode() in body


def test_the_export_is_a_csv_attachment_named_for_the_day_it_was_taken() -> None:
    """B10: the browser saves a dated file instead of rendering the text in a tab."""
    response = _export_response(Client())

    assert response.headers["Content-Type"] == "text/csv; charset=utf-8"
    disposition = response.headers["Content-Disposition"]
    assert disposition.startswith("attachment; ")
    found = _FILENAME.search(disposition)
    assert found is not None
    assert re.fullmatch(r"servicos-\d{4}-\d{2}-\d{2}\.csv", found["name"])


def test_the_file_is_dated_in_the_configured_zone_and_never_the_one_the_server_runs_in() -> None:
    """I4: the time zone is configuration, so the same instant names two different days under two
    configurations and the server's own zone decides nothing."""
    with override_settings(DEADLINER=_configured(FURTHEST_EAST)):
        east, east_days = _dated_filename(FURTHEST_EAST)
    with override_settings(DEADLINER=_configured(FURTHEST_WEST)):
        west, west_days = _dated_filename(FURTHEST_WEST)

    assert east in east_days
    assert west in west_days
    assert east != west


def _dated_filename(zone: ZoneInfo) -> tuple[str, set[str]]:
    """The name the export offered, beside the names the day it ran could honestly carry.

    The view reads the real clock, so the request is bracketed rather than compared against one
    later reading: a run that straddles midnight in ``zone`` would otherwise fail on the hour and
    not on the behaviour.
    """
    before = datetime.datetime.now(tz=zone).date()
    found = _FILENAME.search(_export_response(Client()).headers["Content-Disposition"])
    after = datetime.datetime.now(tz=zone).date()
    assert found is not None
    return found["name"], {_named_for(before), _named_for(after)}


def _named_for(day: datetime.date) -> str:
    return f"servicos-{day.isoformat()}.csv"


def test_the_export_is_streamed_and_never_built_before_the_response_is_handed_back() -> None:
    """Foundation section 7: it is a single streamed query, so the rows are read while the file
    is being written and never gathered into memory first."""
    _services_named(3)
    response = _export_response(Client())

    assert response.streaming
    assert len(_joined(response).splitlines()) == 4


def test_the_export_costs_no_query_per_row(
    django_assert_max_num_queries: QueryCounter,
    django_assert_num_queries: QueryCounter,
) -> None:
    """Foundation section 7 and section 8: a single streamed query, constant whatever it holds."""
    _services_named(1)
    browser = Client()

    with django_assert_max_num_queries(1) as one_record:
        _consume(browser)

    _services_named(SERVICES_PER_PAGE + 5)

    with django_assert_num_queries(len(one_record.captured_queries)):
        _consume(browser)


def _consume(browser: Client) -> None:
    """Download the whole file, because a streamed response reads nothing until it is iterated."""
    _joined(_export_response(browser))


def test_the_list_offers_the_export_the_owner_asked_for() -> None:
    """Foundation section 7 and section 12: a CSV export button in version 1, in Portuguese."""
    a_service()

    page = Client().get(reverse("service-list")).content.decode()

    assert f'href="{reverse("service-export")}"' in page
    assert "Exportar CSV" in page


def test_the_export_lives_under_the_configured_path_segment() -> None:
    """Foundation section 6: the health endpoint is the single route outside the segment."""
    assert reverse("service-export").startswith(f"/{get_config().secret_path_segment}/")
