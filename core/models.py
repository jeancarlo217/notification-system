from typing import ClassVar

from django.db import models


class Service(models.Model):
    """The flat service record of foundation section 3: one spreadsheet row per service."""

    class Status(models.TextChoices):
        ACTIVE = "active"
        COMPLETED = "completed"

    client = models.TextField()
    description = models.TextField()
    due_date = models.DateField()
    status = models.CharField(max_length=9, choices=Status, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.client}: {self.description} (due {self.due_date})"


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
