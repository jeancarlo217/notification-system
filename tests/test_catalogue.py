"""B12, the service catalogue: two reference tables, seeded once and edited afterwards.

Traces: foundation section 3.1 (what a service is stops being free text and becomes a choice from
a catalogue held in the database, under four rules), section 3.2 (the three categories and fifteen
services the company declares in July 2026), I4 (business values are data, so the catalogue is
rows and never an enumeration compiled into a field) and the structural performance rule of
section 8 (the list and the daily run read in a constant number of queries). Shape:
``specs/adr/0005-service-catalogue.md``.
"""

import datetime
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.test import Client, override_settings
from django.urls import reverse

from core.engine import run_daily_engine
from core.models import CatalogService, Service, ServiceCategory
from deadliner.config import DeadlinerConfig
from tests.builders import (
    a_catalog_service,
    a_category,
    a_service,
    a_submitter,
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

DECLARED_CATALOGUE: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Regularização e Licenciamento",
        (
            "Licenciamentos Ambientais",
            "Cadastro Ambiental Rural (CAR)",
            "Corte de Árvores Nativas (CANI)",
            "Regularização Fundiária",
            "Ratificação: Faixa de Fronteira",
            "Outorga de Recursos Hídricos",
        ),
    ),
    (
        "Geotecnologias",
        (
            "Georreferenciamento",
            "Sensoriamento Remoto",
            "Agricultura de Precisão",
            "Projetos de Drenagem",
        ),
    ),
    (
        "Sustentabilidade e ESG",
        (
            "Diagnóstico Global ESG",
            "Inventário de GEE",
            "Levantamento de Estoque de Carbono",
            "Planos de Descarbonização",
            "Geração de Créditos de Carbono",
        ),
    ),
)

# Fixtures that exercise a constraint must build their own rows, and the seed migration already
# holds every name in the table above, so these four are deliberately outside it.
UNDECLARED_CATEGORY = "Perícia Ambiental"
UNDECLARED_SERVICE = "Laudo de Impacto"
ANOTHER_UNDECLARED_SERVICE = "Parecer Técnico"

DECLARED_CATEGORIES = [category for category, _ in DECLARED_CATALOGUE]
DECLARED_PAIRS = [
    (category, service) for category, services in DECLARED_CATALOGUE for service in services
]

QueryCounter = Callable[..., AbstractContextManager[Any]]


def _page(client: Client, name: str, *args: int) -> str:
    return client.get(reverse(name, args=args)).content.decode()


def _reads(captured: Any) -> int:
    """How many times the block asked the database for rows.

    A run writes one row per warning it sends, so the total query count grows with the work done;
    what must not grow with the number of records is how often the data is read (section 8).
    """
    return len(
        [
            query
            for query in captured.captured_queries
            if query["sql"].lstrip().upper().startswith("SELECT")
        ]
    )


def test_a_category_persists_its_name_position_and_active_flag() -> None:
    """Foundation section 3.1: the catalogue is data in two tables, not code."""
    ServiceCategory.objects.create(name=UNDECLARED_CATEGORY, position=99)

    stored = ServiceCategory.objects.get(name=UNDECLARED_CATEGORY)

    assert stored.position == 99
    assert stored.is_active is True


def test_a_catalogue_entry_persists_its_category_name_position_and_active_flag() -> None:
    """Foundation section 3.1 rule 1: a service record references the catalogue service, and the
    category it hangs from is navigation."""
    category = a_category(UNDECLARED_CATEGORY, position=99)

    CatalogService.objects.create(category=category, name=UNDECLARED_SERVICE, position=1)

    stored = CatalogService.objects.get(name=UNDECLARED_SERVICE)
    assert stored.category == category
    assert stored.position == 1
    assert stored.is_active is True


def test_a_catalogue_entry_reserves_the_identifier_ecobalance_will_assign_it() -> None:
    """Foundation section 3.1 rule 4: the reserved column makes the later switch a backfill."""
    entry = a_catalog_service("Georreferenciamento", category="Geotecnologias")

    entry.ecobalance_service_id = 42
    entry.save(update_fields=["ecobalance_service_id"])

    assert CatalogService.objects.get(pk=entry.pk).ecobalance_service_id == 42


def test_two_unmapped_catalogue_entries_do_not_collide_with_each_other() -> None:
    """ADR 0005: the reserved column is unique when set, so the many rows that carry no
    Ecobalance identifier yet must coexist rather than compete for one empty value."""
    category = a_category(UNDECLARED_CATEGORY, position=99)

    CatalogService.objects.create(category=category, name=UNDECLARED_SERVICE, position=1)
    CatalogService.objects.create(category=category, name=ANOTHER_UNDECLARED_SERVICE, position=2)

    unmapped = CatalogService.objects.filter(category=category, ecobalance_service_id=None)
    assert unmapped.count() == 2


def test_the_seeded_catalogue_carries_no_ecobalance_identifier_yet() -> None:
    """ADR 0005: the column is null in all fifteen rows on delivery and stays null until
    Ecobalance's catalog package exists; the backfill is a later command, not a redesign."""
    assert CatalogService.objects.exclude(ecobalance_service_id=None).count() == 0


def test_two_catalogue_entries_cannot_claim_one_ecobalance_identifier() -> None:
    """Foundation section 3.1 rule 4: the reserved identifier maps one row to one row, or the
    later join produces duplicates instead of a backfill."""
    category = a_category(UNDECLARED_CATEGORY, position=99)
    CatalogService.objects.create(
        category=category, name=UNDECLARED_SERVICE, position=1, ecobalance_service_id=7
    )

    with pytest.raises(IntegrityError):
        CatalogService.objects.create(
            category=category, name=ANOTHER_UNDECLARED_SERVICE, position=2, ecobalance_service_id=7
        )


def test_two_categories_cannot_share_a_name() -> None:
    """Foundation section 3.1: the catalogue is a fixed vocabulary, and two menus with one name
    are the ambiguity it exists to remove."""
    ServiceCategory.objects.create(name=UNDECLARED_CATEGORY, position=99)

    with pytest.raises(IntegrityError):
        ServiceCategory.objects.create(name=UNDECLARED_CATEGORY, position=98)


def test_two_services_cannot_share_a_name_inside_one_category() -> None:
    """Foundation section 3.1 rule 3: a name is unique inside its category."""
    category = a_category(UNDECLARED_CATEGORY, position=99)
    CatalogService.objects.create(category=category, name=UNDECLARED_SERVICE, position=1)

    with pytest.raises(IntegrityError):
        CatalogService.objects.create(category=category, name=UNDECLARED_SERVICE, position=2)


def test_one_service_name_is_free_to_repeat_across_two_categories() -> None:
    """Foundation section 3.1 rule 3, the quiet side: uniqueness is inside the category, so two
    menus may legitimately offer the same word."""
    a_catalog_service("Georreferenciamento", category="Geotecnologias")
    a_catalog_service("Georreferenciamento", category="Sustentabilidade e ESG")

    assert CatalogService.objects.filter(name="Georreferenciamento").count() == 2


def test_deleting_a_catalogue_entry_a_deadline_points_at_is_refused() -> None:
    """Foundation section 3.1 rule 3 and ADR 0005: deactivation is the supported operation,
    because a cascade here silently deletes the deadlines this product exists to prevent."""
    entry = a_catalog_service("Georreferenciamento", category="Geotecnologias")
    service = a_service(catalog_service=entry)

    with pytest.raises(ProtectedError):
        entry.delete()

    assert Service.objects.filter(pk=service.pk).exists()
    assert CatalogService.objects.filter(pk=entry.pk).exists()


def test_deleting_a_category_a_catalogue_entry_belongs_to_is_refused() -> None:
    """ADR 0005: both foreign keys are PROTECT, so reorganising a menu cannot take the rows
    underneath it with them."""
    category = a_category("Geotecnologias", position=2)
    entry = a_catalog_service("Georreferenciamento", category="Geotecnologias")

    with pytest.raises(ProtectedError):
        category.delete()

    assert CatalogService.objects.filter(pk=entry.pk).exists()
    assert ServiceCategory.objects.filter(pk=category.pk).exists()


def test_the_migrations_seed_the_three_declared_categories_in_their_declared_order() -> None:
    """Foundation section 3.2: the July 2026 declaration is what the system is built against,
    and a later correction is an edit through the administration site, never a code change."""
    seeded = list(ServiceCategory.objects.order_by("position").values_list("name", flat=True))

    assert seeded == DECLARED_CATEGORIES


def test_the_migrations_seed_the_fifteen_declared_services_in_their_declared_order() -> None:
    """Foundation section 3.2: fifteen services under three categories, spelled as declared."""
    seeded = list(
        CatalogService.objects.order_by("category__position", "position").values_list(
            "category__name", "name"
        )
    )

    assert seeded == DECLARED_PAIRS


def test_a_service_names_what_it_is_through_the_catalogue_and_not_through_free_text() -> None:
    """Foundation section 3: the record carries the service chosen from the catalogue and an
    optional free text observation beside it."""
    entry = a_catalog_service("Inventário de GEE", category="Sustentabilidade e ESG")

    a_service(catalog_service=entry, notes="Escopo 1 e 2 apenas")

    stored = Service.objects.get()
    assert stored.catalog_service == entry
    assert stored.notes == "Escopo 1 e 2 apenas"


def test_a_service_is_valid_without_an_observation() -> None:
    """ADR 0005: the free text that used to name the service becomes optional."""
    candidate = Service(
        client="Fazenda Boa Vista",
        catalog_service=a_catalog_service(),
        start_date=datetime.date(2026, 12, 25),
        term_days=0,
        submitter=a_submitter(),
    )

    candidate.full_clean()

    assert candidate.notes == ""


def test_a_service_without_a_catalogue_entry_is_invalid() -> None:
    """Foundation section 3.1: what a service is stops being free text, so a record with no
    catalogue entry says nothing about what is owed."""
    candidate = Service(
        client="Fazenda Boa Vista",
        due_date=datetime.date(2026, 12, 25),
        submitter=a_submitter(),
    )

    with pytest.raises(ValidationError) as error:
        candidate.full_clean()

    assert "catalog_service" in error.value.message_dict


def test_registering_a_service_persists_the_client_catalogue_entry_notes_and_due_date(
    client: Client,
) -> None:
    """B12: the registration form asks for four business fields and all four reach the record."""
    entry = a_catalog_service("Georreferenciamento", category="Geotecnologias")

    client.post(
        reverse("service-create"),
        registration_payload(catalog_service=str(entry.pk), notes="Area de 320 hectares"),
    )

    stored = Service.objects.get()
    assert stored.client == "Fazenda Boa Vista"
    assert stored.catalog_service == entry
    assert stored.notes == "Area de 320 hectares"
    assert stored.due_date == datetime.date(2026, 12, 25)


def test_a_registration_without_an_observation_is_accepted(client: Client) -> None:
    """ADR 0005: the observation is for detail the catalogue cannot express, so it is optional."""
    client.post(reverse("service-create"), registration_payload(notes=""))

    assert Service.objects.get().notes == ""


def test_a_registration_naming_no_catalogue_entry_creates_nothing(client: Client) -> None:
    """Foundation section 3.1: the catalogue entry is what the record is about, so it is
    required and an empty one is a refused submission."""
    response = client.post(reverse("service-create"), registration_payload(catalog_service=""))

    assert response.status_code == 200
    assert Service.objects.count() == 0


def test_the_registration_page_offers_every_declared_catalogue_service(client: Client) -> None:
    """Foundation section 3.2: the employee picks from the fifteen the company declares."""
    page = _page(client, "service-create")

    for _, service in DECLARED_PAIRS:
        assert service in page


def test_the_registration_page_groups_the_catalogue_under_its_three_categories(
    client: Client,
) -> None:
    """Foundation section 3.1 rule 1: category is navigation, so it organises the menu the
    employee reads without ever reaching the record."""
    page = _page(client, "service-create")

    for category in DECLARED_CATEGORIES:
        assert f'<optgroup label="{category}">' in page


def test_a_deactivated_catalogue_entry_is_not_offered_for_registration(client: Client) -> None:
    """Foundation section 3.1 rule 3: a service the company stops offering is deactivated, and
    deactivation means it disappears from the menu."""
    retired = a_catalog_service("Sensoriamento Remoto", category="Geotecnologias")
    retired.is_active = False
    retired.save(update_fields=["is_active"])

    assert "Sensoriamento Remoto" not in _page(client, "service-create")


def test_a_deactivated_catalogue_entry_is_refused_when_posted(client: Client) -> None:
    """Foundation section 3.1 rule 3: the menu is closed on the server, where it actually binds,
    so a stale page cannot register a service the company no longer offers."""
    retired = a_catalog_service("Sensoriamento Remoto", category="Geotecnologias")
    retired.is_active = False
    retired.save(update_fields=["is_active"])

    response = client.post(
        reverse("service-create"), registration_payload(catalog_service=str(retired.pk))
    )

    assert response.status_code == 200
    assert Service.objects.count() == 0


def test_a_record_pointing_at_a_deactivated_entry_still_shows_what_it_is(client: Client) -> None:
    """Foundation section 3.1 rule 3: deadlines already point at it, which is the whole reason
    deactivation exists instead of deletion."""
    retired = a_catalog_service("Sensoriamento Remoto", category="Geotecnologias")
    a_service(catalog_service=retired)
    retired.is_active = False
    retired.save(update_fields=["is_active"])

    assert "Sensoriamento Remoto" in _page(client, "service-list")


def test_a_record_pointing_at_a_deactivated_entry_is_still_editable(client: Client) -> None:
    """Foundation section 3: a human still moves the due date of a record whose catalogue entry
    the company retired, or deactivation would be deletion by another name."""
    retired = a_catalog_service("Sensoriamento Remoto", category="Geotecnologias")
    service = a_service(catalog_service=retired)
    retired.is_active = False
    retired.save(update_fields=["is_active"])

    response = client.post(
        reverse("service-due-date", args=[service.pk]), edit_payload(start_date="2027-01-10")
    )

    service.refresh_from_db()
    assert response.status_code == 302
    assert service.due_date == datetime.date(2027, 1, 10)


@override_settings(DEADLINER=TEST_DEADLINER)
def test_a_record_pointing_at_a_deactivated_entry_still_earns_its_warnings() -> None:
    """ADR 0005: deactivation removes a service from the menu and does nothing else, so a
    deadline already tracked keeps being warned about. Silently stopping the warnings is the
    failure mode this product exists to prevent."""
    retired = a_catalog_service("Sensoriamento Remoto", category="Geotecnologias")
    a_service(catalog_service=retired, due_date=datetime.date(2026, 12, 25))
    retired.is_active = False
    retired.save(update_fields=["is_active"])
    provider = FakeProvider()

    run_daily_engine(provider=provider, today=datetime.date(2026, 12, 15))

    assert provider.deliveries == ["Fazenda Boa Vista|Sensoriamento Remoto|2026-12-25|10"]


def test_a_service_under_an_inactive_category_is_not_offered_for_registration(
    client: Client,
) -> None:
    """ADR 0005: a service is offered when it is active and its category is active, so retiring
    a whole category takes every service under it out of the menu at once."""
    category = a_category("Geotecnologias", position=2)
    a_catalog_service("Sensoriamento Remoto", category="Geotecnologias")
    category.is_active = False
    category.save(update_fields=["is_active"])

    assert "Sensoriamento Remoto" not in _page(client, "service-create")


def test_a_record_under_an_inactive_category_still_shows_what_it_is(client: Client) -> None:
    """ADR 0005: an inactive category hides its services from the registration form and hides
    nothing else, exactly as when the service itself is deactivated."""
    category = a_category("Geotecnologias", position=2)
    a_service(catalog_service=a_catalog_service("Sensoriamento Remoto", category="Geotecnologias"))
    category.is_active = False
    category.save(update_fields=["is_active"])

    assert "Sensoriamento Remoto" in _page(client, "service-list")


def test_a_record_under_an_inactive_category_is_still_editable(client: Client) -> None:
    """ADR 0005: reorganising the menu must never reach a tracked deadline, so a human still
    moves the due date of a record whose category the company retired."""
    category = a_category("Geotecnologias", position=2)
    entry = a_catalog_service("Sensoriamento Remoto", category="Geotecnologias")
    service = a_service(catalog_service=entry)
    category.is_active = False
    category.save(update_fields=["is_active"])

    response = client.post(
        reverse("service-due-date", args=[service.pk]), edit_payload(start_date="2027-01-10")
    )

    service.refresh_from_db()
    assert response.status_code == 302
    assert service.due_date == datetime.date(2027, 1, 10)


@override_settings(DEADLINER=TEST_DEADLINER)
def test_a_record_under_an_inactive_category_still_earns_its_warnings() -> None:
    """ADR 0005: records under a retired category keep earning warnings, because a menu edit
    that quietly silenced a deadline would be the worst outcome in this file."""
    category = a_category("Geotecnologias", position=2)
    entry = a_catalog_service("Sensoriamento Remoto", category="Geotecnologias")
    a_service(catalog_service=entry, due_date=datetime.date(2026, 12, 25))
    category.is_active = False
    category.save(update_fields=["is_active"])
    provider = FakeProvider()

    run_daily_engine(provider=provider, today=datetime.date(2026, 12, 15))

    assert provider.deliveries == ["Fazenda Boa Vista|Sensoriamento Remoto|2026-12-25|10"]


@override_settings(DEADLINER=TEST_DEADLINER)
def test_the_warning_text_names_the_catalogue_entry_and_not_the_observation() -> None:
    """ADR 0005: the engine renders {service} from the catalogue name; the message template
    contract of ADR 0001 keeps its four fields and no configured template breaks."""
    a_service(
        catalog_service=a_catalog_service("Outorga de Recursos Hídricos"),
        notes="Protocolo interno 4471",
        due_date=datetime.date(2026, 12, 25),
    )
    provider = FakeProvider()

    run_daily_engine(provider=provider, today=datetime.date(2026, 12, 15))

    assert provider.deliveries == ["Fazenda Boa Vista|Outorga de Recursos Hídricos|2026-12-25|10"]


def test_the_list_costs_the_same_queries_for_thirty_records_as_for_one(
    client: Client,
    django_assert_max_num_queries: QueryCounter,
    django_assert_num_queries: QueryCounter,
) -> None:
    """Foundation section 8: reaching the category and service names through a join is the only
    shape that survives; one query per row would grow with the dataset."""
    a_service(client="Cliente 0")

    with django_assert_max_num_queries(10) as one_record:
        client.get(reverse("service-list"))

    for number in range(1, 30):
        a_service(client=f"Cliente {number}")

    with django_assert_num_queries(len(one_record.captured_queries)):
        client.get(reverse("service-list"))


@override_settings(DEADLINER=TEST_DEADLINER)
def test_a_daily_run_reads_the_same_number_of_times_for_thirty_services_as_for_one(
    django_assert_max_num_queries: QueryCounter,
) -> None:
    """Foundation section 8 and ADR 0005: the run selects the catalogue name in the same query as
    the records, so the daily engine does not walk the table once per warning."""
    a_service(client="Cliente 0")

    with django_assert_max_num_queries(20) as one_service:
        run_daily_engine(provider=FakeProvider(), today=datetime.date(2026, 12, 18))

    for number in range(1, 30):
        a_service(client=f"Cliente {number}")

    with django_assert_max_num_queries(300) as thirty_services:
        run_daily_engine(provider=FakeProvider(), today=datetime.date(2026, 12, 18))

    assert _reads(thirty_services) == _reads(one_service)


def test_the_administration_site_registers_the_catalogue_models() -> None:
    """ADR 0005: the catalogue is edited through the administration site once the migration has
    seeded it, and that sentence is only true if a human has a screen."""
    assert admin.site.is_registered(ServiceCategory)
    assert admin.site.is_registered(CatalogService)
