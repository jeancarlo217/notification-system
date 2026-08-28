"""B10, the CSV export.

Traces: foundation section 7 (one CSV button in version 1, one row per service record with every
business field, a single streamed query), section 3 (the flat record is a spreadsheet row by
construction, which the export proves continuously), section 12 (the interface is in Portuguese)
and the performance rule of section 8 (a constant number of queries, never one per row).
"""

import datetime
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from typing import Any, cast
from zoneinfo import ZoneInfo

import pytest
from django.http import StreamingHttpResponse
from django.test import Client
from django.urls import reverse

from core.export import ExportRecord, export_rows
from core.models import Service

CAMPO_GRANDE = ZoneInfo("America/Campo_Grande")

RECORD = ExportRecord(
    client="Fazenda Boa Vista",
    description="Renovacao de licenca ambiental",
    due_date=datetime.date(2026, 12, 25),
    status_label="Ativo",
    created_at=datetime.datetime(2026, 8, 28, 9, 30, tzinfo=CAMPO_GRANDE),
)


def _registered(client_name: str = "Fazenda Boa Vista") -> Service:
    return Service.objects.create(
        client=client_name,
        description="Renovacao de licenca ambiental",
        due_date=datetime.date(2026, 12, 25),
    )


def _downloaded(client: Client) -> str:
    # The test client is typed as a buffered response; the view returns a streaming one.
    response = cast(StreamingHttpResponse, client.get(reverse("service-export")))
    chunks = cast(Iterator[bytes], response.streaming_content)
    return b"".join(chunks).decode("utf-8")


def test_the_export_opens_with_a_header_naming_every_business_field() -> None:
    """Foundation section 7: every business field of the flat record, and nothing else."""
    assert list(export_rows([])) == [
        ("Cliente", "Serviço", "Vencimento", "Status", "Cadastrado em")
    ]


def test_the_export_writes_one_row_per_service_record() -> None:
    """Foundation section 3: a flat record is a spreadsheet row, one for one."""
    rows = list(export_rows([RECORD, RECORD]))

    assert len(rows) == 3


def test_the_due_date_is_written_the_way_a_brazilian_spreadsheet_reads_it() -> None:
    """Foundation section 12: the file is read by the same people who read the screens."""
    _, row = export_rows([RECORD])

    assert row[2] == "25/12/2026"


def test_the_creation_time_is_written_with_the_hour_it_happened_locally() -> None:
    """Foundation section 5: the company's day is the America/Campo_Grande day."""
    _, row = export_rows([RECORD])

    assert row[4] == "28/08/2026 09:30"


def test_the_status_is_written_in_portuguese() -> None:
    """Foundation section 12: Ativo and Concluído, the same words the list shows."""
    _, row = export_rows([RECORD])

    assert row[3] == "Ativo"


@pytest.mark.django_db
def test_the_list_offers_the_export_in_one_click(client: Client) -> None:
    """Foundation section 7: a button, which is the whole interface this feature has."""
    page = client.get(reverse("service-list")).content.decode()

    assert reverse("service-export") in page
    assert "Exportar" in page


@pytest.mark.django_db
def test_the_export_arrives_as_a_downloadable_spreadsheet_file(client: Client) -> None:
    """Foundation section 7: it downloads as a file, it does not render as a page."""
    response = client.get(reverse("service-export"))

    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("text/csv")
    assert "attachment" in response.headers["Content-Disposition"]


@pytest.mark.django_db
def test_the_export_carries_every_registered_record(client: Client) -> None:
    """Foundation section 7: the whole dataset, which is what makes it an export."""
    _registered("Fazenda Boa Vista")
    _registered("Sitio Santa Fe")

    body = _downloaded(client)

    assert "Fazenda Boa Vista" in body
    assert "Sitio Santa Fe" in body


@pytest.mark.django_db
def test_the_export_carries_completed_records_as_well_as_active_ones(client: Client) -> None:
    """Foundation section 7: the export is the dataset, not the work still owed."""
    completed = _registered("Sitio Santa Fe")
    completed.status = Service.Status.COMPLETED
    completed.save()

    assert "Concluído" in _downloaded(client)


@pytest.mark.django_db
def test_the_file_opens_in_a_spreadsheet_that_expects_the_local_conventions(
    client: Client,
) -> None:
    """Foundation section 7: one click means it opens, not that it needs an import wizard."""
    _registered()

    body = _downloaded(client)

    assert body.startswith("﻿")
    assert "Cliente;Serviço;Vencimento;Status;Cadastrado em" in body


@pytest.mark.django_db
def test_the_export_streams_instead_of_building_the_whole_file_first(client: Client) -> None:
    """Foundation section 7: a single streamed query, never a body assembled in memory."""
    response = client.get(reverse("service-export"))

    assert response.streaming


@pytest.mark.django_db
def test_the_export_reads_in_a_constant_number_of_queries_regardless_of_size(
    client: Client,
    django_assert_max_num_queries: Callable[[int], AbstractContextManager[Any]],
) -> None:
    """Foundation section 8: thirty rows cost the same queries as one, never one per row."""
    for number in range(30):
        _registered(f"Cliente {number}")

    with django_assert_max_num_queries(2):
        _downloaded(client)
