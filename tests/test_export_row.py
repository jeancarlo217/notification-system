"""The exported row, as a pure decision (backlog B10).

Traces: foundation section 7 (one row per service record with every business field), section 3
(the record is flat, so a row is a row by construction), section 3.3 with ADR 0007 (the start
date and the term are the two facts, and the derived due date rides beside them), section 12 (the
file an employee opens is in Portuguese) and specs/testing.md, which names CSV row shaping as one
of this project's pure decisions: plain data in, plain data out, no database and no clock, and it
carries the bulk of these tests.
"""

import datetime
from zoneinfo import ZoneInfo

from core.export import (
    EXPORT_HEADER,
    ExportedService,
    csv_line,
    export_filename,
    export_row,
)
from core.terms import due_date_from

CAMPO_GRANDE = ZoneInfo("America/Campo_Grande")
START_DATE = datetime.date(2026, 9, 5)
DUE_DATE = datetime.date(2026, 9, 25)
CREATED_AT = datetime.datetime(2026, 8, 31, 2, 30, tzinfo=datetime.UTC)


def a_record(
    *,
    client: str = "Fazenda Boa Vista",
    category: str = "Regularização e Licenciamento",
    service: str = "Licenciamentos Ambientais",
    notes: str = "Renovação anual",
    start_date: datetime.date = START_DATE,
    term_days: int = 20,
    due_date: datetime.date = DUE_DATE,
    status: str = "Ativo",
    submitter: str = "José Victor",
    created_at: datetime.datetime = CREATED_AT,
) -> ExportedService:
    """One exportable record, every field filled with a value a reader can recognise."""
    return ExportedService(
        client=client,
        category=category,
        service=service,
        notes=notes,
        start_date=start_date,
        term_days=term_days,
        due_date=due_date,
        status=status,
        submitter=submitter,
        created_at=created_at,
    )


def test_the_header_names_every_business_field_of_the_record() -> None:
    """Foundation section 7 and section 12: every business field, named in Portuguese."""
    assert EXPORT_HEADER == (
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


def test_a_row_carries_one_value_for_every_column_the_header_names() -> None:
    """Foundation section 3: the record is flat, so a row never grows or shrinks a column."""
    assert len(export_row(a_record(), CAMPO_GRANDE)) == len(EXPORT_HEADER)


def test_a_row_carries_the_business_fields_in_the_order_the_header_names_them() -> None:
    """Foundation section 7: one row per record with every business field, in one order."""
    assert export_row(a_record(), CAMPO_GRANDE) == (
        "Fazenda Boa Vista",
        "Regularização e Licenciamento",
        "Licenciamentos Ambientais",
        "Renovação anual",
        "05/09/2026",
        "20",
        "25/09/2026",
        "Ativo",
        "José Victor",
        "30/08/2026 22:30",
    )


def test_the_row_carries_the_derived_due_date_beside_the_two_facts_it_comes_from() -> None:
    """ADR 0007: the deadline is derived, and it is what the warnings measure against, so the
    person sorting the spreadsheet finds it in the row rather than computing it again."""
    started, term = datetime.date(2026, 1, 20), 20
    row = export_row(
        a_record(start_date=started, term_days=term, due_date=due_date_from(started, term)),
        CAMPO_GRANDE,
    )

    assert row[EXPORT_HEADER.index("Data de início")] == "20/01/2026"
    assert row[EXPORT_HEADER.index("Prazo (dias)")] == "20"
    assert row[EXPORT_HEADER.index("Vencimento")] == "09/02/2026"


def test_the_created_timestamp_is_printed_in_the_time_zone_it_is_given() -> None:
    """I4: the time zone is configuration, so a record stored at 02:30 UTC is reported as the
    evening before in Campo Grande, which is the day the company was working."""
    stored = datetime.datetime(2026, 8, 31, 2, 30, tzinfo=datetime.UTC)

    row = export_row(a_record(created_at=stored), CAMPO_GRANDE)

    assert row[EXPORT_HEADER.index("Cadastrado em")] == "30/08/2026 22:30"


def test_the_created_timestamp_follows_a_different_configured_zone() -> None:
    """I4 acceptance for this decision: two zones, two reported moments, no code change."""
    stored = datetime.datetime(2026, 8, 31, 2, 30, tzinfo=datetime.UTC)

    campo = export_row(a_record(created_at=stored), CAMPO_GRANDE)
    lisbon = export_row(a_record(created_at=stored), ZoneInfo("Europe/Lisbon"))

    moment = EXPORT_HEADER.index("Cadastrado em")
    assert campo[moment] == "30/08/2026 22:30"
    assert lisbon[moment] == "31/08/2026 03:30"


def test_an_empty_observation_leaves_an_empty_column_and_never_a_missing_one() -> None:
    """Foundation section 3: the observation is optional, and a flat row keeps its shape."""
    row = export_row(a_record(notes=""), CAMPO_GRANDE)

    assert row[EXPORT_HEADER.index("Observação")] == ""
    assert len(row) == len(EXPORT_HEADER)


def test_a_completed_record_reports_the_status_it_is_shown_under() -> None:
    """Foundation section 3: status is the whole lifecycle, so the file has to carry it."""
    row = export_row(a_record(status="Concluído"), CAMPO_GRANDE)

    assert row[EXPORT_HEADER.index("Status")] == "Concluído"


def test_a_line_separates_its_values_with_the_semicolon() -> None:
    """B10: a comma separated file opens as a single column in a pt-BR spreadsheet."""
    assert csv_line(("a", "b", "c")) == "a;b;c\r\n"


def test_a_value_holding_the_separator_stays_one_column() -> None:
    """B10: the observation is free text an employee types, semicolons included."""
    line = csv_line(("Fazenda Boa Vista", "Renovação; ver processo 123"))

    assert line == 'Fazenda Boa Vista;"Renovação; ver processo 123"\r\n'


def test_a_value_holding_a_quote_or_a_line_break_stays_one_column() -> None:
    """B10: free text carries whatever a keyboard produces, and the file survives it."""
    line = csv_line(('diz "urgente"', "primeira\nsegunda"))

    assert line == '"diz ""urgente""";"primeira\nsegunda"\r\n'


def test_the_file_is_named_for_the_day_it_was_exported() -> None:
    """B10: the file lands in a downloads folder beside the ones exported before it."""
    assert export_filename(datetime.date(2026, 8, 31)) == "servicos-2026-08-31.csv"
