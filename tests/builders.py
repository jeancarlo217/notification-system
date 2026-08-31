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
DEFAULT_CLIENT = "Fazenda Boa Vista"
DEFAULT_DUE_DATE = datetime.date(2026, 12, 25)


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
    due_date: datetime.date = DEFAULT_DUE_DATE,
    status: str = "active",
    submitter: Submitter | None = None,
) -> Service:
    """One valid tracked deadline, with its catalogue entry and its submitter resolved."""
    return Service.objects.create(
        client=client,
        catalog_service=catalog_service if catalog_service is not None else a_catalog_service(),
        notes=notes,
        due_date=due_date,
        status=status,
        submitter=submitter if submitter is not None else a_submitter(),
    )


def registration_payload(**overrides: Any) -> dict[str, Any]:
    """What a browser posts to register a service, valid unless a caller breaks one field."""
    payload: dict[str, Any] = {
        "client": DEFAULT_CLIENT,
        "catalog_service": str(a_catalog_service().pk),
        "notes": "Renovacao anual",
        "due_date": "2026-12-25",
        "submitter": DEFAULT_SUBMITTER,
    }
    payload.update(overrides)
    return payload
