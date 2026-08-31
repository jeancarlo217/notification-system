"""The exported row and the line it becomes (backlog B10, foundation section 7).

A pure decision: plain data in, plain data out, no database and no clock, which is the shape
``specs/testing.md`` names for CSV row shaping. It imports nothing from Django, the way
``core/identity.py`` and ``core/terms.py`` do, so anything can call it.
"""

import csv
import datetime
import io
from collections.abc import Sequence
from dataclasses import dataclass

EXPORT_HEADER: tuple[str, ...] = (
    "Cliente",
    "Categoria",
    "Serviço",
    "Observação",
    "Data de início",
    "Prazo (dias)",
    "Vencimento",
    "Status",
    "Responsável",
    "Cadastrado em",
)
"""What each exported column is called, in the language the file is read in (section 12)."""

# The semicolon and not the comma: a spreadsheet under a pt-BR locale splits on the list
# separator of that locale, so a comma separated file opens as one column. Not an I4 value, which
# governs the business values the foundation names, and a field separator is not one of them.
FIELD_DELIMITER = ";"

# Excel reads a file with no byte order mark in the system code page, so "José" arrives as
# "JosÃ©". Deleting this because it looks like stray whitespace is what breaks every accented name.
BYTE_ORDER_MARK = "\ufeff"

_DATE_FORMAT = "%d/%m/%Y"
_MOMENT_FORMAT = "%d/%m/%Y %H:%M"


@dataclass(frozen=True, slots=True)
class ExportedService:
    """The slice of a persisted service that one exported row is made of.

    ``status`` is the label the record is shown under rather than the stored value, so the file
    and the screen name a lifecycle the same way.
    """

    client: str
    category: str
    service: str
    notes: str
    start_date: datetime.date
    term_days: int
    due_date: datetime.date
    status: str
    submitter: str
    created_at: datetime.datetime


def export_row(record: ExportedService, timezone: datetime.tzinfo) -> tuple[str, ...]:
    """One record as one row, in the order ``EXPORT_HEADER`` names its columns.

    The derived due date rides beside the start date and the term it comes from (ADR 0007), and
    the creation moment is reported in ``timezone``, which is configuration (I4).
    """
    return (
        record.client,
        record.category,
        record.service,
        record.notes,
        record.start_date.strftime(_DATE_FORMAT),
        str(record.term_days),
        record.due_date.strftime(_DATE_FORMAT),
        record.status,
        record.submitter,
        record.created_at.astimezone(timezone).strftime(_MOMENT_FORMAT),
    )


def csv_line(values: Sequence[str]) -> str:
    """``values`` as one delimited line, every value that holds a separator, a quote or a line
    break quoted so that it stays one column."""
    buffer = io.StringIO()
    csv.writer(buffer, delimiter=FIELD_DELIMITER).writerow(values)
    return buffer.getvalue()


def export_filename(day: datetime.date) -> str:
    """The name the file is offered under, dated so that yesterday's export is still findable."""
    return f"servicos-{day.isoformat()}.csv"
