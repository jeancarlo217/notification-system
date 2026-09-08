"""The start date and the term: what an employee types, and the deadline derived from it.

Traces: the owner decision of 2026-08-31 (the employee types a date and a number of days instead
of a due date, and the deadline is the first plus the second), foundation section 3 (the due date
is a persisted fact of the flat record), foundation section 12 (the interface is in Portuguese),
I1 and I3 (the engine derives what is owed from the persisted due date, so the derivation has to
have happened by the time a row exists) and I4 (the term is data on the record).
"""

import datetime
from zoneinfo import ZoneInfo

import pytest
from django.contrib import admin
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import Client, override_settings
from django.urls import reverse

from core.engine import run_daily_engine
from core.forms import ServiceEditForm
from core.models import Service
from deadliner.config import DeadlinerConfig
from tests.builders import (
    a_catalog_service,
    a_service,
    a_submitter,
    edit_payload,
    registration_payload,
)
from tests.fakes import FakeProvider

pytestmark = pytest.mark.django_db

TEST_DEADLINER = DeadlinerConfig(
    alert_thresholds=(30, 7, 0),
    whatsapp_destination="5567999998888",
    message_template="{client}|{service}|{due_date}|{days_remaining}",
    secret_path_segment="fake-segment-for-tests",
    timezone=ZoneInfo("America/Campo_Grande"),
)


def _page(client: Client, name: str, *args: int) -> str:
    return client.get(reverse(name, args=args)).content.decode()


def _as_administrator(client: Client) -> None:
    client.force_login(User.objects.create_superuser(username="dona", password="segredo"))


def _admin_change_payload(service: Service, **overrides: str) -> dict[str, str]:
    payload = {
        "client": service.client,
        "catalog_service": str(service.catalog_service_id),
        "notes": service.notes,
        "start_date": service.start_date.isoformat(),
        "term_days": str(service.term_days),
        "status": service.status,
        "submitter": str(service.submitter_id),
    }
    payload.update(overrides)
    return payload


def test_a_service_persists_the_start_date_and_the_term_it_was_registered_with() -> None:
    """Owner decision, 2026-08-31: the two the employee types are facts of the record, so the
    screen that edits them can show back what was entered."""
    a_service(start_date=datetime.date(2026, 9, 5), term_days=20)

    stored = Service.objects.get()

    assert stored.start_date == datetime.date(2026, 9, 5)
    assert stored.term_days == 20


def test_a_service_derives_its_due_date_from_its_start_date_and_its_term() -> None:
    """Owner decision, 2026-08-31: typing the 5th with a term of 20 days is due 20 days later."""
    a_service(start_date=datetime.date(2026, 9, 5), term_days=20)

    stored = Service.objects.get()

    assert stored.due_date == datetime.date(2026, 9, 25)


def test_the_derived_due_date_is_stored_and_can_be_filtered_on_in_the_database() -> None:
    """Foundation section 8: the engine, the uniqueness rule of I1, the ordering and the search
    all reach the due date through the database, so it is a column and never a Python property."""
    a_service(start_date=datetime.date(2026, 9, 5), term_days=20)

    assert Service.objects.filter(due_date=datetime.date(2026, 9, 25)).count() == 1


def test_moving_the_start_date_recomputes_the_due_date() -> None:
    """Owner decision, 2026-08-31: the deadline is derived on every write, so an edit of what it
    derives from cannot leave a stale date behind."""
    service = a_service(start_date=datetime.date(2026, 9, 5), term_days=20)

    service.start_date = datetime.date(2026, 9, 10)
    service.save()

    service.refresh_from_db()
    assert service.due_date == datetime.date(2026, 9, 30)


def test_changing_the_term_recomputes_the_due_date() -> None:
    """Owner decision, 2026-08-31: the other half of the derivation moves the deadline too."""
    service = a_service(start_date=datetime.date(2026, 9, 5), term_days=20)

    service.term_days = 30
    service.save()

    service.refresh_from_db()
    assert service.due_date == datetime.date(2026, 10, 5)


def test_a_due_date_written_by_hand_is_replaced_by_the_derivation() -> None:
    """Owner decision, 2026-08-31: the column is derived, so a value assigned to it directly is
    a lie the next write corrects rather than a second way to set the deadline."""
    service = a_service(start_date=datetime.date(2026, 9, 5), term_days=20)

    service.due_date = datetime.date(2030, 1, 1)
    service.save()

    service.refresh_from_db()
    assert service.due_date == datetime.date(2026, 9, 25)


def test_a_write_naming_its_own_fields_still_recomputes_the_due_date() -> None:
    """Owner decision, 2026-08-31, with the precedent of ADR 0006: the derivation is a property
    of the table, so a caller naming update_fields cannot know to add the derived column and the
    model adds it."""
    service = a_service(start_date=datetime.date(2026, 9, 5), term_days=20)

    service.start_date = datetime.date(2026, 9, 10)
    service.save(update_fields=["start_date"])

    service.refresh_from_db()
    assert service.due_date == datetime.date(2026, 9, 30)


def test_completing_a_service_leaves_its_deadline_where_it_was() -> None:
    """I1 and I3, the quiet side: a save that names only the status must not move a deadline,
    or completing a record would re fire or lose the warnings computed from it."""
    service = a_service(start_date=datetime.date(2026, 9, 5), term_days=20)

    service.status = Service.Status.COMPLETED
    service.save(update_fields=["status"])

    service.refresh_from_db()
    assert service.due_date == datetime.date(2026, 9, 25)


def test_a_service_without_a_start_date_is_invalid() -> None:
    """Owner decision, 2026-08-31: a deadline with nothing to derive it from is not a record."""
    candidate = Service(
        client="Fazenda Boa Vista",
        catalog_service=a_catalog_service(),
        term_days=20,
        submitter=a_submitter(),
    )

    with pytest.raises(ValidationError) as error:
        candidate.full_clean()

    assert "start_date" in error.value.message_dict


def test_a_service_without_a_term_is_invalid() -> None:
    """Owner decision, 2026-08-31: the other half of the derivation is required for the same
    reason, and a term is never guessed at."""
    candidate = Service(
        client="Fazenda Boa Vista",
        catalog_service=a_catalog_service(),
        start_date=datetime.date(2026, 9, 5),
        submitter=a_submitter(),
    )

    with pytest.raises(ValidationError) as error:
        candidate.full_clean()

    assert "term_days" in error.value.message_dict


def test_a_negative_term_is_invalid() -> None:
    """Owner decision, 2026-08-31: a term runs forward from the start date, so a negative one
    would compute a deadline before the service began."""
    candidate = Service(
        client="Fazenda Boa Vista",
        catalog_service=a_catalog_service(),
        start_date=datetime.date(2026, 9, 5),
        term_days=-5,
        submitter=a_submitter(),
    )

    with pytest.raises(ValidationError) as error:
        candidate.full_clean()

    assert "term_days" in error.value.message_dict


def test_registering_a_service_derives_its_due_date_from_what_was_typed(client: Client) -> None:
    """Owner decision, 2026-08-31: the deadline the company is warned about is the start date
    plus the term the employee entered."""
    client.post(
        reverse("service-create"),
        registration_payload(start_date="2026-09-05", term_days="20"),
    )

    stored = Service.objects.get()

    assert stored.start_date == datetime.date(2026, 9, 5)
    assert stored.term_days == 20
    assert stored.due_date == datetime.date(2026, 9, 25)


def test_a_registration_with_a_negative_term_creates_nothing(client: Client) -> None:
    """Owner decision, 2026-08-31: the term runs forward, and the form refuses one that does
    not, on the server where it actually binds."""
    response = client.post(reverse("service-create"), registration_payload(term_days="-5"))

    assert response.status_code == 200
    assert Service.objects.count() == 0


def test_a_registration_with_no_term_creates_nothing(client: Client) -> None:
    """Owner decision, 2026-08-31: the term is half the derivation, so it is required."""
    response = client.post(reverse("service-create"), registration_payload(term_days=""))

    assert response.status_code == 200
    assert Service.objects.count() == 0


def test_the_edit_form_asks_for_the_start_date_and_the_term_and_never_the_due_date() -> None:
    """Owner decision, 2026-08-31: the screen that moved a due date moves the two the deadline
    derives from, because editing the derived column directly would be undone by the next save.
    B23 widened that screen to the whole record and left this unchanged."""
    fields = set(ServiceEditForm().fields)

    assert {"start_date", "term_days"} <= fields
    assert "due_date" not in fields


def test_editing_the_start_date_and_the_term_recomputes_the_stored_due_date(
    client: Client,
) -> None:
    """Foundation section 3: a human moves the deadline, now by moving what derives it."""
    service = a_service(start_date=datetime.date(2026, 9, 5), term_days=20)

    response = client.post(
        reverse("service-edit", args=[service.pk]),
        edit_payload(start_date="2026-10-01", term_days="10"),
    )

    service.refresh_from_db()
    assert response.status_code == 302
    assert service.due_date == datetime.date(2026, 10, 11)


def test_the_edit_screen_offers_the_stored_start_date_and_term(client: Client) -> None:
    """Foundation section 12: the employee sees what was entered before changing it."""
    service = a_service(start_date=datetime.date(2026, 9, 5), term_days=20)

    page = _page(client, "service-edit", service.pk)

    assert 'value="05/09/2026"' in page
    assert 'value="20"' in page


@override_settings(DEADLINER=TEST_DEADLINER)
def test_a_service_earns_its_warnings_from_the_derived_deadline() -> None:
    """I3: what is owed is computed from the persisted due date, so the derivation has to have
    happened by the time the engine reads the row."""
    a_service(start_date=datetime.date(2026, 12, 5), term_days=20)
    provider = FakeProvider()

    run_daily_engine(provider=provider, today=datetime.date(2026, 12, 15))

    assert provider.deliveries == ["Fazenda Boa Vista|Licenciamentos Ambientais|2026-12-25|10"]


def test_the_administration_site_registers_the_service_record() -> None:
    """Owner decision, 2026-08-31: the administration site shows and edits the two new fields,
    which is only true once a human has a screen."""
    assert admin.site.is_registered(Service)


def test_the_administration_site_edits_the_start_date_and_the_term(client: Client) -> None:
    """Owner decision, 2026-08-31: the two the employee types are what an administrator repairs
    when a record is wrong."""
    service = a_service(start_date=datetime.date(2026, 9, 5), term_days=20)
    _as_administrator(client)

    page = client.get(reverse("admin:core_service_change", args=[service.pk])).content.decode()

    assert 'name="start_date"' in page
    assert 'name="term_days"' in page


def test_the_administration_site_never_offers_the_derived_due_date_as_an_input(
    client: Client,
) -> None:
    """Owner decision, 2026-08-31: a hand edit of a derived column is a lie waiting to be
    discovered, so the maintenance door reads the deadline and never writes it."""
    service = a_service()
    _as_administrator(client)

    page = client.get(reverse("admin:core_service_change", args=[service.pk])).content.decode()

    assert 'name="due_date"' not in page


def test_a_deadline_posted_to_the_administration_site_loses_to_the_derivation(
    client: Client,
) -> None:
    """Owner decision, 2026-08-31, with the precedent of ADR 0006: the derivation is a property
    of the table, so it holds whichever door the row came through, this one included."""
    service = a_service(start_date=datetime.date(2026, 9, 5), term_days=20)
    _as_administrator(client)

    client.post(
        reverse("admin:core_service_change", args=[service.pk]),
        _admin_change_payload(service, term_days="30", due_date="2030-01-01"),
    )

    service.refresh_from_db()
    assert service.due_date == datetime.date(2026, 10, 5)
