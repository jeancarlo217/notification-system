"""B14, interface refactor: the three screens, and the combobox widgets the next task will assign.

Traces: foundation section 1 (the audience is the employees of one company, reaching a form and a
list through a private link), section 6 (there is no login, so every screen is reached by its own
route), section 8 (server-rendered Django templates, and a listing that reads in a constant number
of queries) and section 12 (the interface is in Portuguese).

The widgets are exercised through the throwaway forms defined here, never by editing
``core/forms.py``: B14 delivers the widget, the next task assigns it to a field.
"""

import pytest
from django import forms
from django.template.loader import render_to_string
from django.test import Client
from django.urls import reverse

from core.models import Service
from core.widgets import ComboboxWidget, CreatableComboboxWidget
from tests.builders import a_service

CATALOG = [
    ("licenca", "Licença ambiental"),
    ("outorga", "Outorga de água"),
    ("relatorio", "Relatório anual"),
]
KNOWN_NAMES = ["José Silva", "Ana Souza"]

pytestmark = pytest.mark.django_db


class CatalogForm(forms.Form):
    """A throwaway form: it exists so the widgets can be exercised outside ``core.forms`` (B14)."""

    catalog = forms.ChoiceField(choices=CATALOG, label="Serviço", widget=ComboboxWidget)
    submitter = forms.CharField(
        label="Responsável", widget=CreatableComboboxWidget(suggestions=KNOWN_NAMES)
    )


class ObservationForm(forms.Form):
    """A throwaway form carrying the free text field the next task adds to the registration."""

    observation = forms.CharField(label="Observação", required=False, widget=forms.Textarea)


def _registered(client_name: str = "Fazenda Boa Vista") -> Service:
    return a_service(client=client_name)


def _page(client: Client, name: str, *args: int) -> str:
    return client.get(reverse(name, args=args)).content.decode()


def test_the_closed_combobox_renders_every_option_of_its_field() -> None:
    """B14: the catalog is chosen from what the field offers, so all of it has to be there."""
    rendered = str(CatalogForm()["catalog"])

    for value, label in CATALOG:
        assert f'value="{value}"' in rendered
        assert label in rendered


def test_the_closed_combobox_marks_the_stored_option_as_selected() -> None:
    """B14: reopening a record shows what it already holds, never an empty control."""
    rendered = str(CatalogForm(initial={"catalog": "outorga"})["catalog"])

    assert 'value="outorga" selected' in rendered


def test_the_closed_combobox_posts_through_a_control_carrying_the_field_name() -> None:
    """B14: the value rides on a real form control, so a browser with no scripts still posts it."""
    rendered = str(CatalogForm()["catalog"])

    assert "<select" in rendered
    assert 'name="catalog"' in rendered


def test_the_closed_combobox_accepts_an_option_posted_as_a_browser_without_scripts_would() -> None:
    """B14: the enhancement changes what a person sees, never what the form receives."""
    form = CatalogForm({"catalog": "outorga", "submitter": "José Silva"})

    assert form.is_valid()
    assert form.cleaned_data["catalog"] == "outorga"


def test_the_closed_combobox_refuses_a_value_that_is_not_an_option() -> None:
    """B14: the closed combobox is closed on the server too, where the decision actually binds."""
    form = CatalogForm({"catalog": "inventado", "submitter": "José Silva"})

    assert not form.is_valid()
    assert "catalog" in form.errors


def test_the_creatable_combobox_offers_every_known_value_as_a_suggestion() -> None:
    """B14: the known names are reachable without typing them, with or without the script."""
    rendered = str(CatalogForm()["submitter"])

    assert "<datalist" in rendered
    for name in KNOWN_NAMES:
        assert f'value="{name}"' in rendered


def test_the_creatable_combobox_binds_its_input_to_its_own_suggestion_list() -> None:
    """B14: without the script the native suggestions only appear if the two ids agree."""
    rendered = str(CatalogForm()["submitter"])

    assert 'list="id_submitter-options"' in rendered
    assert 'id="id_submitter-options"' in rendered


def test_the_creatable_combobox_accepts_a_value_that_matches_no_suggestion() -> None:
    """B14: a name nobody registered yet is the point of the creatable one; it posts verbatim."""
    form = CatalogForm({"catalog": "outorga", "submitter": "Marina Nogueira"})

    assert form.is_valid()
    assert form.cleaned_data["submitter"] == "Marina Nogueira"


def test_the_creatable_combobox_accepts_a_listed_value_unchanged() -> None:
    """B14: picking a known name posts that name, accents and all."""
    form = CatalogForm({"catalog": "outorga", "submitter": "José Silva"})

    assert form.is_valid()
    assert form.cleaned_data["submitter"] == "José Silva"


def test_a_refused_form_gives_back_the_value_the_person_typed() -> None:
    """B14: a rejected submission never costs the typing that produced it."""
    form = CatalogForm({"catalog": "", "submitter": "Marina Nogueira"})

    assert not form.is_valid()
    assert 'value="Marina Nogueira"' in str(form["submitter"])


def test_the_closed_combobox_keeps_the_categories_a_grouped_field_declares() -> None:
    """B14: a catalogue arrives grouped by category, and the grouping is part of the choice."""

    class GroupedForm(forms.Form):
        catalog = forms.ChoiceField(
            choices=[("Licenciamento", CATALOG[:2]), ("Monitoramento", CATALOG[2:])],
            widget=ComboboxWidget,
        )

    rendered = str(GroupedForm()["catalog"])

    assert '<optgroup label="Licenciamento">' in rendered
    assert '<optgroup label="Monitoramento">' in rendered


def test_the_creatable_combobox_reads_its_suggestions_at_every_render() -> None:
    """B14: the known names live in the database and grow, so a list frozen at import is wrong."""
    names = ["Ana Souza"]

    class LiveForm(forms.Form):
        submitter = forms.CharField(widget=CreatableComboboxWidget(suggestions=lambda: names))

    first = str(LiveForm()["submitter"])
    names.append("Marina Nogueira")
    second = str(LiveForm()["submitter"])

    assert "Marina Nogueira" not in first
    assert "Marina Nogueira" in second


def test_two_comboboxes_on_one_page_never_share_an_identifier() -> None:
    """B14: two instances on one screen must not steer each other, so nothing is global."""
    rendered = str(CatalogForm()["catalog"]) + str(CatalogForm(prefix="segundo")["catalog"])

    assert 'id="id_catalog"' in rendered
    assert 'id="id_segundo-catalog"' in rendered


def test_the_registration_screen_names_its_action_and_its_way_back(client: Client) -> None:
    """Foundation section 12: the employee reads what the button does and how to give up."""
    page = _page(client, "service-create")

    assert "Cadastrar serviço" in page
    assert "Cadastrar" in page
    assert "Cancelar" in page
    assert f'href="{reverse("service-list")}"' in page


def test_the_due_date_screen_names_its_action_and_its_way_back(client: Client) -> None:
    """Foundation section 3: the due date edit is its own screen, with its own verb."""
    service = _registered()

    page = _page(client, "service-due-date", service.pk)

    assert "Editar vencimento" in page
    assert "Salvar" in page
    assert "Cancelar" in page


def test_the_list_screen_names_its_five_columns_in_portuguese(client: Client) -> None:
    """Foundation section 12: the dataset the company works from is labelled in its language."""
    _registered()

    page = _page(client, "service-list")

    for heading in ("Cliente", "Serviço", "Vencimento", "Status", "Ações"):
        assert heading in page


def test_a_listed_service_links_to_its_due_date_edit_and_to_its_completion(
    client: Client,
) -> None:
    """Foundation section 3: both lifecycle actions are reachable from the row they act on."""
    service = _registered()

    page = _page(client, "service-list")

    assert f'href="{reverse("service-due-date", args=[service.pk])}"' in page
    assert f'action="{reverse("service-complete", args=[service.pk])}"' in page
    assert "Concluir" in page


def test_the_list_screen_offers_the_registration_screen(client: Client) -> None:
    """Foundation section 1: the list is where a new record starts."""
    _registered()

    page = _page(client, "service-list")

    assert "Novo serviço" in page
    assert f'href="{reverse("service-create")}"' in page


def test_an_empty_list_says_so_and_still_offers_the_registration_screen(client: Client) -> None:
    """B14: the first employee to open the tool finds a way in, not a blank page."""
    page = _page(client, "service-list")

    assert "Nenhum serviço cadastrado." in page
    assert f'href="{reverse("service-create")}"' in page


def test_a_listed_row_states_its_table_roles(client: Client) -> None:
    """B14: the small layout lays the table out as blocks, which drops the implicit roles."""
    _registered()

    page = _page(client, "service-list")

    assert 'role="table"' in page
    assert 'role="row"' in page
    assert 'role="columnheader"' in page
    assert 'role="cell"' in page


def test_every_screen_asks_a_phone_to_render_it_at_its_own_width(client: Client) -> None:
    """B14: employees use this on a phone as often as on a desktop."""
    for page in (_page(client, "service-list"), _page(client, "service-create")):
        assert 'name="viewport"' in page
        assert "width=device-width" in page


def test_every_screen_carries_its_styles_and_its_script_inline(client: Client) -> None:
    """B14: gunicorn serves no static file in the stack, so a linked asset would be a 404."""
    page = _page(client, "service-create")

    assert "<style" in page
    assert "<script" in page
    assert "/static/" not in page
    assert "<script src=" not in page
    assert "<link rel=" not in page


def test_the_interface_answers_to_the_reader_system_colour_setting(client: Client) -> None:
    """B14: the owner asked for both themes, chosen by the device rather than by a switch."""
    page = _page(client, "service-list")

    assert "prefers-color-scheme: dark" in page


def test_a_free_text_field_renders_as_a_labelled_textarea_in_the_form_layout() -> None:
    """B14: the free text observation the next task adds is a first class control here."""
    rendered = render_to_string(
        "core/service_form.html",
        {"form": ObservationForm(), "title": "Cadastrar serviço", "action": "Cadastrar"},
    )

    assert "<textarea" in rendered
    assert "Observação" in rendered
    assert 'class="field"' in rendered


def test_a_textarea_can_only_be_resized_vertically(client: Client) -> None:
    """B14: a textarea dragged wider would break the layout sideways on every screen size."""
    page = _page(client, "service-create")

    assert "resize: vertical" in page
