"""The forms an employee uses: registration (B4, B12, B13), and the record edit (B23)."""

from collections.abc import Iterator
from itertools import groupby
from typing import TYPE_CHECKING, Any, ClassVar, cast

from django import forms
from django.db import transaction
from django.db.models import Q, QuerySet
from django.forms.models import ModelChoiceIterator

from core.identity import normalize_person_name
from core.models import CatalogService, Service, Submitter
from core.widgets import BrazilianDateWidget, ComboboxWidget, CreatableComboboxWidget

if TYPE_CHECKING:
    ServiceModelForm = forms.ModelForm[Service]
    CatalogServiceChoiceField = forms.ModelChoiceField[CatalogService]
    CatalogServiceIterator = ModelChoiceIterator[CatalogService]
else:
    # The stubs make these generic; the runtime classes are not subscriptable.
    ServiceModelForm = forms.ModelForm
    CatalogServiceChoiceField = forms.ModelChoiceField
    CatalogServiceIterator = ModelChoiceIterator


# The board has not settled the final wording, so the two labels live here and the two forms
# that show them read this one copy.
TERM_LABELS = {"start_date": "Data de início", "term_days": "Prazo (dias)"}


BRAZILIAN_DATE_FORMAT = "%d/%m/%Y"
"""How a date is written and read on every screen, which is how the country writes it."""

DATE_HELP_TEXT = "Formato dia, mês e ano, por exemplo 05/09/2026."
"""The tooltip a browser shows when it refuses the pattern; the widget carries the spoken one."""


def _date_input() -> forms.DateInput:
    """A date the employee types, never one the browser draws.

    Deliberately not ``type="date"``: that widget is rendered in the browser's own interface
    locale and never in the document's, so an employee on an English browser is shown
    ``mm/dd/yyyy``, types the day first as anybody here would, and the browser reads it as the
    month. Nothing errors and the deadline lands months away (B23). Parsing is unaffected either
    way, because the pt-BR locale already puts ``%d/%m/%Y`` ahead of the ISO form.
    """
    return BrazilianDateWidget(
        format=BRAZILIAN_DATE_FORMAT,
        attrs={
            "inputmode": "numeric",
            "placeholder": "dd/mm/aaaa",
            "autocomplete": "off",
            "maxlength": "10",
            # One or two digits for the day and the month, because `%d/%m/%Y` parses `5/9/2026`
            # and a browser refusing what the server accepts is a worse lie than no refusal.
            "pattern": r"\d{1,2}/\d{1,2}/\d{4}",
            "title": DATE_HELP_TEXT,
        },
    )


def _term_widgets() -> dict[str, object]:
    """The inputs for the start date and the term, one set of instances per form class."""
    return {"start_date": _date_input(), "term_days": forms.NumberInput(attrs={"min": 0})}


OFFERED_CATALOG_ENTRY = Q(is_active=True, category__is_active=True)
"""What the catalogue offers today: an active entry under an active category (ADR 0005)."""


def _catalogue_menu(entries: Q) -> QuerySet[CatalogService]:
    """The matching catalogue entries, ordered the way the grouped menu reads them.

    One ordered query joined to the category, so the menu costs the same at fifteen rows and at
    fifty (foundation section 8).
    """
    return (
        CatalogService.objects.filter(entries)
        .select_related("category")
        .order_by("category__position", "position")
    )


def offered_catalog_services() -> QuerySet[CatalogService]:
    """The catalogue entries the form offers: active, under an active category (ADR 0005)."""
    return _catalogue_menu(OFFERED_CATALOG_ENTRY)


def editable_catalog_services(current_id: int | None) -> QuerySet[CatalogService]:
    """What the catalogue offers, plus the entry this record already holds (B23).

    What the company offers today is the wrong question to ask of a record written before it
    stopped offering something: B20 retired the five ESG services while a tracked deadline points
    at ``Inventário de GEE``, so an edit form built on the offered queryset alone renders that
    field empty and refuses the value the record carries. The record would then be uneditable, or
    saved onto whichever entry the employee picked to get past it. The widening is one row wide,
    it reaches only the record holding that row, and the registration form is untouched by it.
    """
    if current_id is None:
        return offered_catalog_services()
    return _catalogue_menu(OFFERED_CATALOG_ENTRY | Q(pk=current_id))


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


class ServiceRecordForm(ServiceModelForm):
    """The five fields the record holds, as every screen that writes one asks for them.

    One base class and not a copy per screen (B23): registration and the edit show the same
    fields under the same labels through the same widgets, and two copies of a label drift apart
    on the first rename.

    Three fields of the record are never inputs here. Status is the completion action of
    foundation section 3, the submitter belongs to the record rather than to the write (section
    10), and the due date is derived by ``Service.save`` from the start date and the term, so an
    input for it would be undone by the next save (ADR 0007).
    """

    catalog_service = CatalogueChoiceField(
        queryset=offered_catalog_services(),
        label="Serviço",
        empty_label="Selecione o serviço",
        widget=ComboboxWidget,
    )

    class Meta:
        model = Service
        fields: ClassVar[list[str]] = [
            "client",
            "catalog_service",
            "notes",
            "start_date",
            "term_days",
        ]
        labels: ClassVar[dict[str, str]] = {
            "client": "Cliente",
            "notes": "Observação",
            **TERM_LABELS,
        }
        widgets: ClassVar[dict[str, object]] = {
            "client": forms.TextInput,
            "notes": forms.Textarea(attrs={"rows": 6}),
            **_term_widgets(),
        }


class ServiceRegistrationForm(ServiceRecordForm):
    """The registration form of foundation section 3: what the record is, and who entered it.

    It is the record its base asks for plus the one field only registration asks. ``submitter``
    is a declared field and never a Meta one, because what the employee posts is a name, and
    letting the model form build the record from it would assign a string to a foreign key.
    ``save`` resolves it.
    """

    submitter = forms.CharField(
        label="Responsável",
        widget=CreatableComboboxWidget(suggestions=offered_submitter_names),
    )

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


class ServiceEditForm(ServiceRecordForm):
    """One screen for the whole record (B23): every field it holds, filled with what it holds.

    It asks nobody for a name, because attribution is per record and not per edit (ADR 0006),
    and it records no history, which foundation section 10 defers; the audit entry the write
    emits is the whole account of the change (I6).
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Widen the menu by the entry this record holds, and by nothing else (B23).

        ``self.fields`` is this instance's own copy of the class's fields, so the widening lives
        on this form and never reaches the registration form built from the same base.
        """
        super().__init__(*args, **kwargs)
        catalogue = cast(CatalogueChoiceField, self.fields["catalog_service"])
        catalogue.queryset = editable_catalog_services(self.instance.catalog_service_id)
