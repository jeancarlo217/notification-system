"""B23, the date is typed and shown in the order Brazil writes it.

Trace: foundation section 3.3 (the deadline is a start date plus a term, so the start date is one
of the two facts the whole schedule derives from), section 12 (the interface is Portuguese).

The defect this exists against is silent, which is what makes it serious in a product whose
purpose is not to lose a deadline. `input type="date"` is drawn by the browser in the browser's
own interface locale and never in the document's, so an employee on an English browser is shown
`mm/dd/yyyy`, types a date day first as anybody here would, and the browser reads it month first.
Nothing errors. The record is stored four months from where the person meant, and the warning
fires there too.
"""

import datetime
import re

import pytest
from django.test import Client
from django.urls import reverse

from core.models import Service
from tests.builders import a_catalog_service, a_service, a_submitter, registration_payload

pytestmark = pytest.mark.django_db


def _page(name: str, *args: object) -> str:
    return Client().get(reverse(name, args=args)).content.decode()


def _start_date_input(page: str) -> str:
    """The one input tag, because the page also carries a stylesheet that names input types."""
    found = re.search(r'<input[^>]*name="start_date"[^>]*>', page)
    assert found is not None
    return found.group(0)


def test_the_start_date_is_not_drawn_by_the_browser() -> None:
    """B23: a native date input takes its order from the browser locale, which we do not control."""
    page = _page("service-create")

    assert 'type="date"' not in _start_date_input(page)


def test_the_start_date_says_the_order_it_expects() -> None:
    """B23: the field states the format, because nothing else on the screen can."""
    page = _page("service-create")

    assert 'placeholder="dd/mm/aaaa"' in _start_date_input(page)


def test_a_date_typed_day_first_is_stored_day_first() -> None:
    """B23: the acceptance test. The fifth of September is not the ninth of May."""
    service = a_catalog_service()
    a_submitter("José Victor")

    Client().post(
        reverse("service-create"),
        registration_payload(catalog_service=str(service.pk), start_date="05/09/2026"),
    )

    assert Service.objects.get().start_date == datetime.date(2026, 9, 5)


def test_a_date_in_the_machine_format_is_still_accepted() -> None:
    """B23: the browser used to post ISO, and anything that still does must keep working."""
    service = a_catalog_service()
    a_submitter("José Victor")

    Client().post(
        reverse("service-create"),
        registration_payload(catalog_service=str(service.pk), start_date="2026-09-05"),
    )

    assert Service.objects.get().start_date == datetime.date(2026, 9, 5)


def test_a_stored_date_is_shown_back_in_the_order_it_was_typed() -> None:
    """B23: a screen that reads a date back differently from how it took it teaches distrust."""
    service = a_service(start_date=datetime.date(2026, 9, 5), term_days=30)

    page = _page("service-edit", service.pk)

    assert 'value="05/09/2026"' in page
