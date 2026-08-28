"""B13, submitter identity: the row a typed name resolves to, and the field that types it.

Traces: foundation section 6 (the registration form asks who is entering the record, offering the
people who already registered something and accepting a name nobody anticipated) and I8 (one
person is one row however their name is spelled, by construction of a uniqueness rule on a
normalized form of the name). Shape: ``specs/adr/0006-submitter-identity.md``.

The normalization rule itself is a pure function and lives in ``tests/test_identity.py``; the
audit entries these submissions write live in ``tests/test_audit.py``, beside I6.
"""

import datetime

import pytest
from django.contrib import admin
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.test import Client
from django.urls import reverse

from core.identity import normalize_person_name
from core.models import Service, Submitter
from tests.builders import a_service, a_submitter, registration_payload

pytestmark = pytest.mark.django_db

SEEDED_NAMES = ["José Victor", "Geovanna"]


def _page(client: Client, name: str, *args: int) -> str:
    return client.get(reverse(name, args=args)).content.decode()


def _register(client: Client, submitter: str) -> None:
    client.post(reverse("service-create"), registration_payload(submitter=submitter))


def test_a_submitter_persists_its_display_name_key_and_active_flag() -> None:
    """ADR 0006: identity is a row, carrying the spelling first seen and the key it resolves by."""
    Submitter.objects.create(display_name="Marina Nogueira", normalized_name="marina nogueira")

    stored = Submitter.objects.get(normalized_name="marina nogueira")

    assert stored.display_name == "Marina Nogueira"
    assert stored.is_active is True
    assert stored.created_at is not None


def test_two_submitters_cannot_share_a_normalized_name() -> None:
    """I8: the database constraint is what makes one name one person by construction, rather
    than by the lookup happening to run first."""
    Submitter.objects.create(display_name="Marina Nogueira", normalized_name="marina nogueira")

    with pytest.raises(IntegrityError):
        Submitter.objects.create(display_name="MARINA NOGUEIRA", normalized_name="marina nogueira")


def test_the_migrations_seed_the_two_people_who_enter_most_records() -> None:
    """Foundation section 6: the field offers the people who already registered something,
    starting with José Victor and Geovanna."""
    seeded = {
        submitter.display_name
        for submitter in Submitter.objects.filter(
            normalized_name__in=[normalize_person_name(name) for name in SEEDED_NAMES]
        )
    }

    assert seeded == set(SEEDED_NAMES)


def test_two_spellings_of_one_name_resolve_to_one_submitter_row(client: Client) -> None:
    """I8: José Victor and jose  victor are one employee, so the second submission finds the
    first one's row instead of writing a second."""
    before = Submitter.objects.count()

    _register(client, "José Victor")
    _register(client, "jose  victor")

    key = normalize_person_name("José Victor")
    assert Submitter.objects.count() == before
    assert Submitter.objects.filter(normalized_name=key).count() == 1


def test_both_records_of_one_person_point_at_the_same_submitter(client: Client) -> None:
    """I8: the identity is a row, so two records entered by one person are joinable by it."""
    _register(client, "Marina Nogueira")
    _register(client, "marina  NOGUEIRA")

    first, second = Service.objects.order_by("pk")

    assert first.submitter_id == second.submitter_id


def test_the_first_spelling_of_a_name_is_the_one_that_stays(client: Client) -> None:
    """ADR 0006: last spelling wins would let one careless entry rename the person everywhere in
    the interface and in every future export."""
    _register(client, "Marina Nogueira")
    _register(client, "MARINA  nogueira")

    resolved = Submitter.objects.get(normalized_name=normalize_person_name("Marina Nogueira"))

    assert resolved.display_name == "Marina Nogueira"


def test_a_later_submission_does_not_rename_a_seeded_person(client: Client) -> None:
    """ADR 0006: first spelling wins applies to the seeded rows too, so a hurried JOSE VICTOR
    does not rewrite the name the interface shows."""
    _register(client, "JOSE VICTOR")

    resolved = Submitter.objects.get(normalized_name=normalize_person_name("José Victor"))

    assert resolved.display_name == "José Victor"


def test_a_name_nobody_anticipated_creates_a_submitter_and_the_record_points_at_it(
    client: Client,
) -> None:
    """Foundation section 6: the field accepts a name nobody anticipated, typed as plain text and
    saved as typed."""
    _register(client, "Marina Nogueira")

    created = Submitter.objects.get(normalized_name=normalize_person_name("Marina Nogueira"))
    assert created.display_name == "Marina Nogueira"
    assert Service.objects.get().submitter == created


def test_registering_under_a_seeded_name_points_the_record_at_the_seeded_row(
    client: Client,
) -> None:
    """Foundation section 6: picking one of the offered people resolves to the row already
    there, which is what makes the audit trail count a person once."""
    seeded = Submitter.objects.get(normalized_name=normalize_person_name("José Victor"))

    _register(client, "José Victor")

    assert Service.objects.get().submitter == seeded


def test_a_registration_naming_nobody_creates_nothing(client: Client) -> None:
    """Foundation section 6: the field is required, because a record with no submitter is the
    unattributed write I6 exists to prevent."""
    before = Submitter.objects.count()

    response = client.post(reverse("service-create"), registration_payload(submitter=""))

    assert response.status_code == 200
    assert Service.objects.count() == 0
    assert Submitter.objects.count() == before


def test_a_name_of_only_whitespace_creates_nothing(client: Client) -> None:
    """I8: whitespace collapses, so a name made of it names nobody."""
    before = Submitter.objects.count()

    response = client.post(reverse("service-create"), registration_payload(submitter="   "))

    assert response.status_code == 200
    assert Service.objects.count() == 0
    assert Submitter.objects.count() == before


def test_a_name_that_normalizes_to_empty_is_a_validation_error_and_not_a_row(
    client: Client,
) -> None:
    """ADR 0006: the form rejects a value that normalizes to empty. A stray combining mark from a
    broken paste survives ``strip`` and still names nobody, so the rule is the normalized form
    and never the raw string being non-blank."""
    before = Submitter.objects.count()

    response = client.post(reverse("service-create"), registration_payload(submitter="́"))

    assert response.status_code == 200
    assert Service.objects.count() == 0
    assert Submitter.objects.count() == before


def test_deleting_a_submitter_a_record_points_at_is_refused() -> None:
    """ADR 0006: a submitter who leaves the company is deactivated, never deleted, because
    records point at them and a cascade would take the deadlines with the person."""
    submitter = a_submitter("Marina Nogueira")
    service = a_service(submitter=submitter)

    with pytest.raises(ProtectedError):
        submitter.delete()

    assert Service.objects.filter(pk=service.pk).exists()
    assert Submitter.objects.filter(pk=submitter.pk).exists()


def test_the_registration_page_offers_the_people_who_already_registered_something(
    client: Client,
) -> None:
    """Foundation section 6: the field offers the known people, so the common case is a choice
    and not a spelling exercise."""
    page = _page(client, "service-create")

    for name in SEEDED_NAMES:
        assert name in page


def test_the_offered_people_are_ordered_by_the_name_they_are_shown_under(
    client: Client,
) -> None:
    """ADR 0006: the field is a list over the active submitters ordered by display name, so it
    stays readable as the list grows."""
    page = _page(client, "service-create")

    assert page.index("Geovanna") < page.index("José Victor")


def test_a_deactivated_submitter_is_no_longer_offered(client: Client) -> None:
    """ADR 0006: deactivation is what happens to somebody who leaves, and it removes them from
    the field without touching the records that point at them."""
    leaver = a_submitter("Marina Nogueira")
    a_service(submitter=leaver)
    leaver.is_active = False
    leaver.save(update_fields=["is_active"])

    assert "Marina Nogueira" not in _page(client, "service-create")


def test_typing_a_deactivated_persons_name_reuses_their_row(client: Client) -> None:
    """ADR 0006 and I8: deactivation controls what the field offers, never what a name resolves
    to. Minting a second row for one person would break I8 to satisfy a preference about a
    dropdown."""
    leaver = a_submitter("Marina Nogueira")
    leaver.is_active = False
    leaver.save(update_fields=["is_active"])
    before = Submitter.objects.count()

    _register(client, "marina  NOGUEIRA")

    assert Submitter.objects.count() == before
    assert Service.objects.get().submitter == leaver


def test_resolving_a_deactivated_person_does_not_reactivate_them(client: Client) -> None:
    """ADR 0006: resolution never flips is_active back on, so deactivating somebody means stop
    suggesting them and means nothing more than that."""
    leaver = a_submitter("Marina Nogueira")
    leaver.is_active = False
    leaver.save(update_fields=["is_active"])

    _register(client, "Marina Nogueira")

    leaver.refresh_from_db()
    assert leaver.is_active is False


def test_the_registration_form_names_the_submitter_field_in_portuguese(client: Client) -> None:
    """Foundation section 12: the interface is in Portuguese, this field included."""
    assert "Responsável" in _page(client, "service-create")


def test_the_due_date_screen_asks_nobody_for_a_name(client: Client) -> None:
    """ADR 0006: attribution is per record, not per edit, because asking would add friction to a
    two click action and per action attribution is editing history, deferred in section 10."""
    service = a_service()

    page = _page(client, "service-due-date", service.pk)

    assert 'name="submitter"' not in page
    assert "Responsável" not in page


def test_editing_a_due_date_leaves_the_record_pointing_at_who_registered_it(
    client: Client,
) -> None:
    """ADR 0006: the submitter is who registered the service, and an edit does not reassign it."""
    registrant = a_submitter("Marina Nogueira")
    service = a_service(submitter=registrant)

    client.post(reverse("service-due-date", args=[service.pk]), {"due_date": "2027-01-10"})

    service.refresh_from_db()
    assert service.due_date == datetime.date(2027, 1, 10)
    assert service.submitter == registrant


def test_the_administration_site_registers_the_submitter() -> None:
    """ADR 0006: an administrator corrects a bad display name through the administration site,
    which registers Submitter alongside the catalogue models."""
    assert admin.site.is_registered(Submitter)
