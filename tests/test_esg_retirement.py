"""The company stops offering the ESG services, by deactivation and never by deletion.

Traces: foundation section 3.1 rule 3 (a service the company stops offering is deactivated,
never deleted, because deadlines already point at it), ADR 0005 (an inactive category hides every
service under it from the registration form and hides nothing else, and both catalogue foreign
keys are PROTECT) and I3 (a deadline the system knows about keeps earning its warnings).
"""

import datetime
from zoneinfo import ZoneInfo

import pytest
from django.test import Client, override_settings
from django.urls import reverse

from core.engine import run_daily_engine
from core.models import CatalogService, Service, ServiceCategory
from deadliner.config import DeadlinerConfig
from tests.builders import (
    RETIRED_CATEGORY,
    a_catalog_service,
    a_service,
    edit_payload,
    registration_payload,
)
from tests.fakes import FakeProvider

pytestmark = pytest.mark.django_db

TEST_DEADLINER = DeadlinerConfig(
    alert_thresholds=(30, 7, 0),
    whatsapp_number="5567999998888",
    message_template="{client}|{service}|{due_date}|{days_remaining}",
    secret_path_segment="fake-segment-for-tests",
    timezone=ZoneInfo("America/Campo_Grande"),
)

RETIRED_SERVICES = (
    "Diagnóstico Global ESG",
    "Inventário de GEE",
    "Levantamento de Estoque de Carbono",
    "Planos de Descarbonização",
    "Geração de Créditos de Carbono",
)
TRACKED_SERVICE = "Inventário de GEE"


def _page(client: Client, name: str, *args: int) -> str:
    return client.get(reverse(name, args=args)).content.decode()


def _tracked_deadline() -> Service:
    return a_service(
        client="Ceramica Sao Jorge",
        catalog_service=a_catalog_service(TRACKED_SERVICE, category=RETIRED_CATEGORY),
        start_date=datetime.date(2026, 8, 28),
        term_days=0,
    )


def test_the_migrations_deactivate_the_esg_category() -> None:
    """Board decision, 2026-08-31: the company no longer performs the services under this
    heading, and a catalogue that changes is data being edited, never code."""
    category = ServiceCategory.objects.get(name=RETIRED_CATEGORY)

    assert category.is_active is False


def test_the_five_esg_services_still_exist_after_the_retirement() -> None:
    """Foundation section 3.1 rule 3: a service the company stops offering is deactivated, never
    deleted, because deadlines already point at it and both foreign keys are PROTECT."""
    surviving = set(
        CatalogService.objects.filter(category__name=RETIRED_CATEGORY).values_list(
            "name", flat=True
        )
    )

    assert surviving == set(RETIRED_SERVICES)


@pytest.mark.parametrize("service_name", RETIRED_SERVICES)
def test_a_retired_esg_service_is_not_offered_for_registration(
    client: Client, service_name: str
) -> None:
    """ADR 0005: a service is offered when it is active and its category is active, so retiring
    the category takes every service under it out of the menu at once."""
    assert service_name not in _page(client, "service-create")


def test_the_registration_menu_no_longer_names_the_esg_category(client: Client) -> None:
    """ADR 0005: the heading is navigation, and a heading with nothing offered under it is a
    dead entry in the menu the employee reads."""
    assert RETIRED_CATEGORY not in _page(client, "service-create")


def test_a_retired_esg_service_is_refused_when_posted(client: Client) -> None:
    """Foundation section 3.1 rule 3: the menu is closed on the server, where it binds, so a
    stale page cannot register a service the company no longer performs."""
    retired = a_catalog_service(TRACKED_SERVICE, category=RETIRED_CATEGORY)

    response = client.post(
        reverse("service-create"), registration_payload(catalog_service=str(retired.pk))
    )

    assert response.status_code == 200
    assert Service.objects.count() == 0


def test_a_deadline_pointing_at_a_retired_esg_service_still_lists(client: Client) -> None:
    """ADR 0005: an inactive category hides its services from the registration form and hides
    nothing else, so the record the company is tracking keeps showing what it is."""
    _tracked_deadline()

    page = _page(client, "service-list")

    assert "Ceramica Sao Jorge" in page
    assert TRACKED_SERVICE in page


def test_a_deadline_pointing_at_a_retired_esg_service_is_still_editable(client: Client) -> None:
    """Foundation section 3: a human still moves the deadline of a record whose category the
    company retired, or deactivation would be deletion by another name."""
    service = _tracked_deadline()

    response = client.post(
        reverse("service-edit", args=[service.pk]),
        edit_payload(
            catalog_service=str(service.catalog_service_id),
            start_date="2026-09-30",
            term_days="10",
        ),
    )

    service.refresh_from_db()
    assert response.status_code == 302
    assert service.due_date == datetime.date(2026, 10, 10)


def test_the_edit_screen_shows_the_retired_entry_the_record_already_holds(client: Client) -> None:
    """B23: `offered_catalog_services` returns active entries under active categories, and a
    record points at one of the five the company retired. An edit form built on that queryset
    alone renders the field empty, so the employee sees a blank menu over a filled record and
    the next save moves the deadline onto whatever they pick."""
    service = _tracked_deadline()

    page = _page(client, "service-edit", service.pk)

    assert TRACKED_SERVICE in page
    assert f'value="{service.catalog_service_id}" selected' in page


def test_saving_the_edit_screen_untouched_keeps_the_retired_entry(client: Client) -> None:
    """B23 with foundation section 3.1 rule 3: a record the item promises stays editable must
    survive being saved, or deactivation reaches a tracked deadline after all."""
    service = _tracked_deadline()

    response = client.post(
        reverse("service-edit", args=[service.pk]),
        edit_payload(
            client=service.client,
            catalog_service=str(service.catalog_service_id),
            start_date="28/08/2026",
        ),
    )

    service.refresh_from_db()
    assert response.status_code == 302
    assert service.catalog_service.name == TRACKED_SERVICE


def test_the_edit_screen_widens_the_menu_for_nobody_but_the_record_that_holds_it(
    client: Client,
) -> None:
    """B23: the edit form carries the entry its own record holds, and that is the whole of the
    widening. The registration form still offers the retired services to nobody."""
    _tracked_deadline()

    assert TRACKED_SERVICE not in _page(client, "service-create")


@override_settings(DEADLINER=TEST_DEADLINER)
def test_a_deadline_pointing_at_a_retired_esg_service_still_earns_its_warnings() -> None:
    """I3: retiring a menu entry must never silence a deadline the system already knows about,
    which is the exact failure this product exists to prevent."""
    _tracked_deadline()
    provider = FakeProvider()

    run_daily_engine(provider=provider, today=datetime.date(2026, 7, 30))

    assert provider.deliveries == ["Ceramica Sao Jorge|Inventário de GEE|2026-08-28|29"]
