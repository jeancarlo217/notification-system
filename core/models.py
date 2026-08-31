from collections.abc import Iterable
from typing import ClassVar

from django.db import models
from django.db.models.base import ModelBase

from core.identity import normalize_person_name


class ServiceCategory(models.Model):
    """A heading of the service catalogue (foundation section 3.1).

    Navigation only: a tracked deadline references the service, never the category it hangs from,
    so reorganising the menu never reaches a record.
    """

    name = models.TextField(unique=True)
    position = models.PositiveSmallIntegerField()
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.name


class CatalogService(models.Model):
    """One service the company offers, as its catalogue declares it (foundation section 3.1).

    This is what the sister project Ecobalance calls ``Service``; here that name belongs to the
    tracked deadline, and ``ecobalance_service_id`` is the column its identifier lands in.
    """

    category = models.ForeignKey(ServiceCategory, on_delete=models.PROTECT, related_name="services")
    name = models.TextField()
    position = models.PositiveSmallIntegerField()
    is_active = models.BooleanField(default=True)
    ecobalance_service_id = models.PositiveIntegerField(null=True, blank=True, unique=True)

    class Meta:
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["category", "name"], name="one_service_name_per_category"
            )
        ]

    def __str__(self) -> str:
        return f"{self.category.name}: {self.name}"


class Submitter(models.Model):
    """The person a typed name resolves to (foundation section 6).

    ``normalized_name`` is the identity key, derived here from ``display_name`` on every write,
    and its uniqueness is what makes one name one person (I8). ``display_name`` is the spelling
    first seen and is never rewritten by a later submission.
    """

    display_name = models.TextField()
    normalized_name = models.TextField(unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.display_name

    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        """Persist the row with its identity key derived from the name it shows (I8).

        A rename onto somebody who already exists raises ``IntegrityError`` rather than merging
        two people quietly, which is the honest outcome of saying the two rows are one person.
        """
        self.normalized_name = normalize_person_name(self.display_name)
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            # The key is derived, so a caller naming its own fields cannot know to write it.
            update_fields=None if update_fields is None else {*update_fields, "normalized_name"},
        )


class Service(models.Model):
    """The flat service record of foundation section 3: one spreadsheet row per service."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Ativo"
        COMPLETED = "completed", "Concluído"

    client = models.TextField()
    catalog_service = models.ForeignKey(
        CatalogService, on_delete=models.PROTECT, related_name="services"
    )
    notes = models.TextField(blank=True)
    due_date = models.DateField()
    status = models.CharField(max_length=9, choices=Status, default=Status.ACTIVE)
    submitter = models.ForeignKey(Submitter, on_delete=models.PROTECT, related_name="services")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.client}: {self.catalog_service.name} (due {self.due_date})"


class Alert(models.Model):
    """One warning attempt per (service, threshold), unique by construction (I1)."""

    class State(models.TextChoices):
        PENDING = "pending"
        SENT = "sent"
        FAILED = "failed"

    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="alerts")
    threshold = models.PositiveIntegerField()
    state = models.CharField(max_length=7, choices=State, default=State.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["service", "threshold"], name="one_alert_per_service_threshold"
            )
        ]

    def __str__(self) -> str:
        return f"alert {self.threshold}d for service {self.service_id}: {self.state}"
