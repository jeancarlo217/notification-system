"""B7, message rendering: the warning text as a pure function of template and record values.

Traces: foundation section 4 (the template is configuration over the four named fields), I4
(the wording is data, never a literal in code; the exact text is OQ-3 and any template
satisfies these tests).
"""

import datetime

from core.engine import render_message


def test_the_message_renders_the_four_configured_fields() -> None:
    """Foundation section 4: client, service, due date and days remaining, from the record."""
    text = render_message(
        "{client}: {service} vence em {days_remaining} dias ({due_date}).",
        client="Fazenda Boa Vista",
        service="Renovacao de licenca ambiental",
        due_date=datetime.date(2026, 12, 25),
        days_remaining=7,
    )

    assert text == "Fazenda Boa Vista: Renovacao de licenca ambiental vence em 7 dias (2026-12-25)."


def test_a_template_may_use_a_subset_of_the_fields() -> None:
    """I4: the template decides which fields appear; the code imposes none of them."""
    text = render_message(
        "{client} tem prazo em {days_remaining} dias.",
        client="Sitio Santa Fe",
        service="Outorga de uso da agua",
        due_date=datetime.date(2026, 12, 25),
        days_remaining=30,
    )

    assert text == "Sitio Santa Fe tem prazo em 30 dias."


def test_the_template_controls_the_date_format() -> None:
    """I4: the due date reaches the template as a date, so the configuration owns its format."""
    text = render_message(
        "Vence em {due_date:%d/%m/%Y}.",
        client="Fazenda Boa Vista",
        service="Renovacao de licenca ambiental",
        due_date=datetime.date(2026, 12, 25),
        days_remaining=0,
    )

    assert text == "Vence em 25/12/2026."
