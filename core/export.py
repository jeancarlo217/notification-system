"""The CSV export (backlog B10, foundation section 7).

Shaping a record into a spreadsheet row is a decision: plain data in, plain data out, no clock and
no database (specs/testing.md). The view around it owns the streaming and the file headers.
"""

import datetime
from collections.abc import Iterable, Iterator
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExportRecord:
    """One service as the export sees it, with its instant already in the local zone."""

    client: str
    description: str
    due_date: datetime.date
    status_label: str
    created_at: datetime.datetime


EXPORT_HEADER = ("Cliente", "Serviço", "Vencimento", "Status", "Cadastrado em")

CSV_DELIMITER = ";"
"""What a spreadsheet under a pt-BR locale expects as the list separator."""

BYTE_ORDER_MARK = "\ufeff"
"""What the same spreadsheet needs in order to read the accents as UTF-8."""


def export_rows(records: Iterable[ExportRecord]) -> Iterator[tuple[str, ...]]:
    """The header row, then one row per record, in the order the records arrive."""
    yield EXPORT_HEADER
    for record in records:
        yield (
            record.client,
            record.description,
            record.due_date.strftime("%d/%m/%Y"),
            record.status_label,
            record.created_at.strftime("%d/%m/%Y %H:%M"),
        )
