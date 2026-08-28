"""The forms an employee uses: registration with three fields, and a due date edit (B4)."""

from typing import TYPE_CHECKING, ClassVar

from django import forms

from core.models import Service

if TYPE_CHECKING:
    ServiceModelForm = forms.ModelForm[Service]
else:
    # The stubs make ModelForm generic; the runtime class is not subscriptable.
    ServiceModelForm = forms.ModelForm


def _date_input() -> forms.DateInput:
    return forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})


class ServiceRegistrationForm(ServiceModelForm):
    """The three-field form of foundation section 1; status is not an input (section 3)."""

    class Meta:
        model = Service
        fields: ClassVar[list[str]] = ["client", "description", "due_date"]
        labels: ClassVar[dict[str, str]] = {
            "client": "Cliente",
            "description": "Serviço",
            "due_date": "Data de vencimento",
        }
        widgets: ClassVar[dict[str, object]] = {
            "client": forms.TextInput,
            "description": forms.TextInput,
            "due_date": _date_input(),
        }


class DueDateForm(ServiceModelForm):
    """The one-field edit of foundation section 3: a human moves the due date."""

    class Meta:
        model = Service
        fields: ClassVar[list[str]] = ["due_date"]
        labels: ClassVar[dict[str, str]] = {"due_date": "Data de vencimento"}
        widgets: ClassVar[dict[str, object]] = {"due_date": _date_input()}
