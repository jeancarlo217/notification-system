"""The forms an employee uses: registration (B4, B12, B13), and a due date edit (B4)."""

from collections.abc import Iterator
from itertools import groupby
from typing import TYPE_CHECKING, Any, ClassVar

from django import forms
from django.db import transaction
from django.db.models import QuerySet
from django.forms.models import ModelChoiceIterator

from core.identity import normalize_person_name
from core.models import CatalogService, Service, Submitter
from core.widgets import ComboboxWidget, CreatableComboboxWidget

if TYPE_CHECKING:
    ServiceModelForm = forms.ModelForm[Service]
    CatalogServiceChoiceField = forms.ModelChoiceField[CatalogService]
    CatalogServiceIterator = ModelChoiceIterator[CatalogService]
else:
    # The stubs make these generic; the runtime classes are not subscriptable.
    ServiceModelForm = forms.ModelForm
    CatalogServiceChoiceField = forms.ModelChoiceField
    CatalogServiceIterator = ModelChoiceIterator


def _date_input() -> forms.DateInput:
    return forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})


def offered_catalog_services() -> QuerySet[CatalogService]:
    """The catalogue entries the form offers: active, under an active category (ADR 0005).

    One ordered query joined to the category, so the menu costs the same at fifteen rows and at
    fifty (foundation section 8).
    """
    return (
        CatalogService.objects.filter(is_active=True, category__is_active=True)
        .select_related("category")
        .order_by("category__position", "position")
    )


def offered_submitter_names() -> list[str]:
    """The people the submitter field suggests: the active ones, by the name they are shown under.

    Deactivation controls what the field offers and never what a typed name resolves to
    (ADR 0006).
    """
    return list(
        Submitter.objects.filter(is_active=True)
        .order_by("display_name")
        .values_list("display_name", flat=True)
    )


class CategoryGroupedIterator(CatalogServiceIterator):
    """The catalogue as a menu: the entries of one category grouped under its name."""

    def __iter__(self) -> Iterator[tuple[Any, Any]]:
        if self.field.empty_label is not None:
            yield ("", self.field.empty_label)
        # The field is built once at import and rendered for years, so iterating the queryset
        # directly would serve every later request the result cache of the first one.
        for category, entries in groupby(
            self.queryset.iterator(), lambda entry: entry.category.name
        ):
            yield (category, [self.choice(entry) for entry in entries])


class CatalogueChoiceField(CatalogServiceChoiceField):
    """A choice from the offered catalogue, grouped by category and validated against itself.

    The queryset stays lazy and is read at every render, so a row deactivated this morning is
    gone from the menu this afternoon and refused when an old page posts it.
    """

    iterator = CategoryGroupedIterator

    def label_from_instance(self, obj: CatalogService) -> str:
        return obj.name


class ServiceRegistrationForm(ServiceModelForm):
    """The registration form of foundation section 3: what the record is, and who entered it.

    Status is not an input: completion is a later human action.
    """

    catalog_service = CatalogueChoiceField(
        queryset=offered_catalog_services(),
        label="Serviço",
        empty_label="Selecione o serviço",
        widget=ComboboxWidget,
    )
    submitter = forms.CharField(
        label="Responsável",
        widget=CreatableComboboxWidget(suggestions=offered_submitter_names),
    )

    class Meta:
        model = Service
        # ``submitter`` is a declared field and never a Meta one: what the employee posts is a
        # name, and letting the model form build the record from it would assign a string to a
        # foreign key. ``save`` resolves it.
        fields: ClassVar[list[str]] = ["client", "catalog_service", "notes", "due_date"]
        labels: ClassVar[dict[str, str]] = {
            "client": "Cliente",
            "notes": "Observação",
            "due_date": "Data de vencimento",
        }
        widgets: ClassVar[dict[str, object]] = {
            "client": forms.TextInput,
            "notes": forms.Textarea(attrs={"rows": 3}),
            "due_date": _date_input(),
        }

    def clean_submitter(self) -> str:
        """Refuse a name that names nobody, and write nothing (ADR 0006).

        Validation answers whether the input is acceptable; resolving it here would mint a person
        for a submission the form then refuses, who would sit in the suggestion list forever
        having entered nothing.
        """
        typed: str = self.cleaned_data["submitter"]
        if not normalize_person_name(typed):
            raise forms.ValidationError("Este campo é obrigatório.")
        return typed

    def save(self, commit: bool = True) -> Service:
        """Write the record and the person who entered it, together or not at all (ADR 0006).

        The first spelling of a name is the one that stays, and resolving a deactivated person
        reuses their row without reactivating them.
        """
        typed: str = self.cleaned_data["submitter"]
        with transaction.atomic():
            submitter, _ = Submitter.objects.get_or_create(
                normalized_name=normalize_person_name(typed),
                defaults={"display_name": typed.strip()},
            )
            self.instance.submitter = submitter
            return super().save(commit=commit)


class DueDateForm(ServiceModelForm):
    """The one-field edit of foundation section 3: a human moves the due date."""

    class Meta:
        model = Service
        fields: ClassVar[list[str]] = ["due_date"]
        labels: ClassVar[dict[str, str]] = {"due_date": "Data de vencimento"}
        widgets: ClassVar[dict[str, object]] = {"due_date": _date_input()}
