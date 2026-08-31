"""Builders for the persisted records the tests need, so one model change edits one file.

A ``Service`` points at a catalogue entry (ADR 0005) and at a submitter (ADR 0006). Most tests
care about neither: they care about thresholds, dates and screens, and they call ``a_service`` to
get a valid record without restating the references. Tests that are about the catalogue or the
submitter build their own rows and say so.

The reference builders resolve rather than insert, so they find the rows the seeding migrations
already wrote and never duplicate them.
"""

import datetime
from typing import Any

from core.identity import normalize_person_name
from core.models import CatalogService, Service, ServiceCategory, Submitter

DEFAULT_CATEGORY = "Regularização e Licenciamento"
DEFAULT_CATALOG_SERVICE = "Licenciamentos Ambientais"
DEFAULT_SUBMITTER = "José Victor"
# The heading the board retired on 2026-08-31: still seeded, still pointed at by a deadline,
# and no longer offered.
RETIRED_CATEGORY = "Sustentabilidade e ESG"
DEFAULT_CLIENT = "Fazenda Boa Vista"
DEFAULT_START_DATE = datetime.date(2026, 12, 25)
DEFAULT_TERM_DAYS = 0
# A zero term makes the derived due date land on the start date, so every caller that only
# cares about a deadline keeps reading and writing one.
DEFAULT_DUE_DATE = DEFAULT_START_DATE


def a_category(name: str = DEFAULT_CATEGORY, *, position: int = 1) -> ServiceCategory:
    """The catalogue category named ``name``, seeded or created here."""
    category, _ = ServiceCategory.objects.get_or_create(name=name, defaults={"position": position})
    return category


def a_catalog_service(
    name: str = DEFAULT_CATALOG_SERVICE,
    *,
    category: str = DEFAULT_CATEGORY,
    position: int = 1,
) -> CatalogService:
    """The catalogue entry ``name`` inside ``category``, seeded or created here."""
    entry, _ = CatalogService.objects.get_or_create(
        category=a_category(category), name=name, defaults={"position": position}
    )
    return entry


def a_submitter(display_name: str = DEFAULT_SUBMITTER) -> Submitter:
    """The submitter that ``display_name`` resolves to, by the normalization rule of I8."""
    submitter, _ = Submitter.objects.get_or_create(
        normalized_name=normalize_person_name(display_name),
        defaults={"display_name": display_name},
    )
    return submitter


def a_service(
    *,
    client: str = DEFAULT_CLIENT,
    catalog_service: CatalogService | None = None,
    notes: str = "",
    start_date: datetime.date = DEFAULT_START_DATE,
    term_days: int = DEFAULT_TERM_DAYS,
    due_date: datetime.date | None = None,
    status: str = "active",
    submitter: Submitter | None = None,
) -> Service:
    """One valid tracked deadline, with its catalogue entry and its submitter resolved.

    ``due_date`` is the shorthand for the tests that care about the deadline and not about how it
    was reached: it sets the start date to that day with a zero term, and it wins over the two.
    """
    if due_date is not None:
        start_date, term_days = due_date, 0
    return Service.objects.create(
        client=client,
        catalog_service=catalog_service if catalog_service is not None else a_catalog_service(),
        notes=notes,
        start_date=start_date,
        term_days=term_days,
        status=status,
        submitter=submitter if submitter is not None else a_submitter(),
    )


def registration_payload(**overrides: Any) -> dict[str, Any]:
    """What a browser posts to register a service, valid unless a caller breaks one field."""
    payload: dict[str, Any] = {
        "client": DEFAULT_CLIENT,
        "catalog_service": str(a_catalog_service().pk),
        "notes": "Renovacao anual",
        "start_date": DEFAULT_START_DATE.isoformat(),
        "term_days": str(DEFAULT_TERM_DAYS),
        "submitter": DEFAULT_SUBMITTER,
    }
    payload.update(overrides)
    return payload


def edit_payload(**overrides: Any) -> dict[str, Any]:
    """What a browser posts to move a deadline, valid unless a caller breaks one field."""
    payload: dict[str, Any] = {
        "start_date": DEFAULT_START_DATE.isoformat(),
        "term_days": str(DEFAULT_TERM_DAYS),
    }
    payload.update(overrides)
    return payload
