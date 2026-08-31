"""B4, registration and lifecycle: the registration form, the list, a due date edit, completion.

Traces: foundation section 1 (a form with three fields writes flat records and the audience is
employees of one company), section 3 (status is the whole lifecycle; completing a service or
editing its due date is a human action through the form), section 12 (the interface is in
Portuguese) and the performance rule of section 8 (a listing reads in a constant number of
queries, never one per row).
"""

import datetime
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

import pytest
from django.test import Client
from django.urls import reverse

from core.forms import ServiceRegistrationForm
from core.models import Service
from tests.builders import DEFAULT_CATALOG_SERVICE, a_service, registration_payload

pytestmark = pytest.mark.django_db


def _registered(client_name: str = "Fazenda Boa Vista") -> Service:
    return a_service(client=client_name)


def _page(client: Client, name: str, *args: int) -> str:
    return client.get(reverse(name, args=args)).content.decode()


def test_registering_a_service_persists_the_submitted_fields_as_an_active_record(
    client: Client,
) -> None:
    """Foundation section 1: a form in, one flat active record persisted."""
    client.post(reverse("service-create"), registration_payload())

    stored = Service.objects.get()

    assert stored.client == "Fazenda Boa Vista"
    assert stored.catalog_service.name == DEFAULT_CATALOG_SERVICE
    assert stored.due_date == datetime.date(2026, 12, 25)
    assert stored.status == "active"


def test_the_registration_form_asks_for_the_business_fields_and_the_submitter() -> None:
    """Foundation section 3 with ADR 0005 and ADR 0006: the record is the client, the catalogue
    entry, the observation, the due date and who entered it, and nothing else is an input."""
    assert set(ServiceRegistrationForm().fields) == {
        "client",
        "catalog_service",
        "notes",
        "due_date",
        "submitter",
    }


def test_a_successful_registration_returns_to_the_list(client: Client) -> None:
    """B4: after registering, the employee sees the list the new record now belongs to."""
    response = client.post(reverse("service-create"), registration_payload())

    assert response.status_code == 302
    assert response.headers["Location"] == reverse("service-list")


def test_a_registration_missing_a_field_creates_nothing_and_shows_the_form_again(
    client: Client,
) -> None:
    """B4: an incomplete submission is not a record; the form comes back for correction."""
    response = client.post(reverse("service-create"), registration_payload(catalog_service=""))

    assert response.status_code == 200
    assert Service.objects.count() == 0


def test_a_registration_with_an_unreadable_date_creates_nothing(client: Client) -> None:
    """B4: a due date that is not a date cannot be warned about, so it is refused."""
    response = client.post(reverse("service-create"), registration_payload(due_date="amanha"))

    assert response.status_code == 200
    assert Service.objects.count() == 0


def test_a_field_error_is_reported_in_portuguese(client: Client) -> None:
    """Foundation section 12: the interface, errors included, speaks Portuguese."""
    response = client.post(reverse("service-create"), registration_payload(client=""))

    assert "Este campo é obrigatório." in response.content.decode()


def test_registration_cannot_set_the_status_because_the_form_does_not_ask_for_it(
    client: Client,
) -> None:
    """Foundation section 3: completion is a later human action, never a registration input."""
    client.post(reverse("service-create"), registration_payload(status="completed"))

    assert Service.objects.get().status == "active"


def test_the_registration_form_labels_its_fields_in_portuguese(client: Client) -> None:
    """Foundation section 12: the employee reads Cliente, Servico, Observacao and Data de
    vencimento."""
    page = _page(client, "service-create")

    assert "Cliente" in page
    assert "Serviço" in page
    assert "Observação" in page
    assert "Data de vencimento" in page


def test_the_list_shows_every_registered_service(client: Client) -> None:
    """Foundation section 1: the list is the flat dataset the company works from."""
    _registered("Fazenda Boa Vista")
    _registered("Sitio Santa Fe")

    page = _page(client, "service-list")

    assert "Fazenda Boa Vista" in page
    assert "Sitio Santa Fe" in page
    assert DEFAULT_CATALOG_SERVICE in page


def test_the_list_shows_due_dates_in_the_brazilian_format(client: Client) -> None:
    """Foundation section 12: a Portuguese interface writes the date as day, month, year."""
    _registered()

    assert "25/12/2026" in _page(client, "service-list")


def test_the_list_names_the_status_in_portuguese(client: Client) -> None:
    """Foundation section 12: an active record reads Ativo, a completed one reads Concluído."""
    _registered("Fazenda Boa Vista")
    completed = _registered("Sitio Santa Fe")
    completed.status = Service.Status.COMPLETED
    completed.save()

    page = _page(client, "service-list")

    assert "Ativo" in page
    assert "Concluído" in page


def test_the_list_reads_in_a_constant_number_of_queries_regardless_of_size(
    client: Client,
    django_assert_max_num_queries: Callable[[int], AbstractContextManager[Any]],
) -> None:
    """Foundation section 8: thirty rows cost the same queries as one, never one per row."""
    for number in range(30):
        _registered(f"Cliente {number}")

    with django_assert_max_num_queries(3):
        client.get(reverse("service-list"))


def test_completing_a_service_marks_it_completed_and_returns_to_the_list(
    client: Client,
) -> None:
    """Foundation section 3: a renewed or delivered service is marked completed by a human."""
    service = _registered()

    response = client.post(reverse("service-complete", args=[service.pk]))

    service.refresh_from_db()
    assert service.status == "completed"
    assert response.status_code == 302
    assert response.headers["Location"] == reverse("service-list")


def test_completing_leaves_the_other_fields_and_the_other_services_untouched(
    client: Client,
) -> None:
    """Foundation section 3, the quiet side: completion changes one status and nothing else."""
    completed = _registered("Fazenda Boa Vista")
    other = _registered("Sitio Santa Fe")

    client.post(reverse("service-complete", args=[completed.pk]))

    completed.refresh_from_db()
    other.refresh_from_db()
    assert completed.due_date == datetime.date(2026, 12, 25)
    assert other.status == "active"


def test_completing_requires_a_post_so_a_followed_link_cannot_complete(client: Client) -> None:
    """Foundation section 3: completion is a deliberate action, not a page someone opened."""
    service = _registered()

    response = client.get(reverse("service-complete", args=[service.pk]))

    service.refresh_from_db()
    assert response.status_code == 405
    assert service.status == "active"


def test_completing_an_unknown_service_is_not_found(client: Client) -> None:
    """B4: an identifier that matches no record is a 404, never a silent success."""
    response = client.post(reverse("service-complete", args=[9999]))

    assert response.status_code == 404


def test_editing_the_due_date_persists_the_new_date(client: Client) -> None:
    """Foundation section 3: a due date is edited by a human through the form."""
    service = _registered()

    response = client.post(
        reverse("service-due-date", args=[service.pk]), {"due_date": "2027-01-10"}
    )

    service.refresh_from_db()
    assert service.due_date == datetime.date(2027, 1, 10)
    assert response.status_code == 302
    assert response.headers["Location"] == reverse("service-list")


def test_the_due_date_form_changes_the_date_and_nothing_else(client: Client) -> None:
    """Foundation section 3: the due date edit is one field, so the rest cannot drift through it."""
    service = _registered()

    client.post(
        reverse("service-due-date", args=[service.pk]),
        {
            "due_date": "2027-01-10",
            "client": "Outro",
            "notes": "Outro",
            "status": "completed",
        },
    )

    service.refresh_from_db()
    assert service.client == "Fazenda Boa Vista"
    assert service.notes == ""
    assert service.status == "active"


def test_the_due_date_form_offers_the_stored_date_the_way_a_date_input_reads_it(
    client: Client,
) -> None:
    """Foundation section 12: under pt-BR a bound date renders in a form the picker shows empty."""
    service = _registered()

    assert 'value="2026-12-25"' in _page(client, "service-due-date", service.pk)


def test_an_unreadable_due_date_edit_changes_nothing(client: Client) -> None:
    """B4: a refused edit leaves the record as it was and shows the form again."""
    service = _registered()

    response = client.post(reverse("service-due-date", args=[service.pk]), {"due_date": "x"})

    service.refresh_from_db()
    assert response.status_code == 200
    assert service.due_date == datetime.date(2026, 12, 25)


def test_the_due_date_page_of_an_unknown_service_is_not_found(client: Client) -> None:
    """B4: an identifier that matches no record is a 404."""
    response = client.get(reverse("service-due-date", args=[9999]))

    assert response.status_code == 404
