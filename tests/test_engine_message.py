"""B27, message rendering: the deadline phrase and the list text, as pure functions.

Traces: foundation section 4 (the header, the line and the five deadline phrases the owner
approved on 2026-10-27, the header reworded on 2026-11-09), I4 (every word of the message is
configuration; the code only chooses which phrase applies), and rule 8 of backlog B27 (the phrase
is chosen by the sign and the count it is handed is never negative).
"""

import datetime

from core.engine import ListLine, deadline_phrase, render_list
from deadliner.config import DeadlinePhrases

APPROVED_PHRASES = DeadlinePhrases(
    future="vence em {days} dias",
    tomorrow="vence amanhã",
    today="vence hoje",
    yesterday="venceu ontem",
    overdue="venceu há {days} dias",
)
APPROVED_HEADER = "Serviços em aberto, {date:%d/%m/%Y}. {count} serviços nesta lista."
APPROVED_LINE = "• *{client}* | {service} | {deadline} ({due_date:%d/%m/%Y})"
TODAY = datetime.date(2026, 12, 15)


def _line(
    client: str = "Fazenda Boa Vista",
    service: str = "Licenciamentos Ambientais",
    due: datetime.date = datetime.date(2026, 12, 25),
    days_remaining: int = 10,
) -> ListLine:
    return ListLine(client=client, service=service, due_date=due, days_remaining=days_remaining)


def test_a_deadline_two_days_out_or_more_reads_as_the_future_phrase() -> None:
    """B27 rule 8, case one: from two days out the count is printed."""
    assert deadline_phrase(5, APPROVED_PHRASES) == "vence em 5 dias"
    assert deadline_phrase(2, APPROVED_PHRASES) == "vence em 2 dias"


def test_a_deadline_one_day_out_reads_as_tomorrow() -> None:
    """B27 rule 8, case two: never `vence em 1 dias`."""
    assert deadline_phrase(1, APPROVED_PHRASES) == "vence amanhã"


def test_a_deadline_on_the_day_reads_as_today() -> None:
    """B27 rule 8, case three: never `vence em 0 dias`."""
    assert deadline_phrase(0, APPROVED_PHRASES) == "vence hoje"


def test_a_deadline_one_day_past_reads_as_yesterday() -> None:
    """B27 rule 8, case four."""
    assert deadline_phrase(-1, APPROVED_PHRASES) == "venceu ontem"


def test_a_deadline_two_days_past_or_more_reads_as_overdue_with_no_minus_sign() -> None:
    """B27 rule 8, case five: the sign chose the phrase, so the phrase is handed a count."""
    assert deadline_phrase(-3, APPROVED_PHRASES) == "venceu há 3 dias"
    assert deadline_phrase(-2, APPROVED_PHRASES) == "venceu há 2 dias"


def test_the_list_renders_as_the_wording_the_owner_approved() -> None:
    """Foundation section 4: the header, then one line per service, in the order given."""
    lines = (
        _line(
            client="Sitio Santa Fe",
            service="Georreferenciamento",
            due=datetime.date(2026, 12, 12),
            days_remaining=-3,
        ),
        _line(),
    )

    text = render_list(
        lines,
        header=APPROVED_HEADER,
        line_template=APPROVED_LINE,
        phrases=APPROVED_PHRASES,
        today=TODAY,
    )

    assert text == (
        "Serviços em aberto, 15/12/2026. 2 serviços nesta lista.\n"
        "• *Sitio Santa Fe* | Georreferenciamento | venceu há 3 dias (12/12/2026)\n"
        "• *Fazenda Boa Vista* | Licenciamentos Ambientais | vence em 10 dias (25/12/2026)"
    )


def test_the_lines_are_joined_by_one_newline_with_nothing_blank_between_them() -> None:
    """Foundation section 4: items separated by blank lines were rejected on the real phone."""
    lines = (_line(client="Um"), _line(client="Dois"), _line(client="Tres"))

    text = render_list(
        lines, header="{count}", line_template="{client}", phrases=APPROVED_PHRASES, today=TODAY
    )

    assert text == "3\nUm\nDois\nTres"


def test_the_header_counts_the_services_listed() -> None:
    """Foundation section 4, ADR 0001 note of 2026-11-09: `count` is the services in the list."""
    text = render_list(
        (_line(),),
        header="{count} em {date}",
        line_template="{client}",
        phrases=APPROVED_PHRASES,
        today=TODAY,
    )

    assert text == "1 em 2026-12-15\nFazenda Boa Vista"


def test_a_line_template_may_use_a_subset_of_the_fields() -> None:
    """I4: the template decides which fields appear; the code imposes none of them."""
    text = render_list(
        (_line(),),
        header="{count}",
        line_template="{client}: {days_remaining}",
        phrases=APPROVED_PHRASES,
        today=TODAY,
    )

    assert text == "1\nFazenda Boa Vista: 10"


def test_the_template_controls_the_date_format() -> None:
    """I4: the due date reaches the template as a date, so the configuration owns its format."""
    text = render_list(
        (_line(),),
        header="{count}",
        line_template="{due_date:%d/%m/%Y}|{due_date}",
        phrases=APPROVED_PHRASES,
        today=TODAY,
    )

    assert text == "1\n25/12/2026|2026-12-25"
