"""The interface: the three screens, the combobox widgets, and B16 brand, theme and assets.

Traces: foundation section 1 (the audience is the employees of one company, reaching a form and a
list through a private link), section 6 (there is no login, so every screen is reached by its own
route, and the health endpoint is the single route outside the secret path segment), section 8
(server-rendered Django templates, and a listing that reads in a constant number of queries) and
section 12 (the interface is in Portuguese).

The widgets are exercised through the throwaway forms defined here, never by editing
``core/forms.py``: B14 delivers the widget, the next task assigns it to a field.
"""

import re

import pytest
from django import forms
from django.conf import settings
from django.contrib.staticfiles import finders
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


def _rule_body(css: str, selector: str, holding: str) -> str:
    """The declarations of the rule opened by ``selector`` whose body mentions ``holding``."""
    start = 0
    while True:
        opening = css.index("{", css.index(selector, start))
        depth, cursor = 1, opening + 1
        while depth:
            depth += {"{": 1, "}": -1}.get(css[cursor], 0)
            cursor += 1
        body = css[opening + 1 : cursor - 1]
        if holding in body:
            return body
        start = opening + 1


def _declarations(body: str) -> dict[str, str]:
    return {name: value.strip() for name, value in re.findall(r"(--[\w-]+)\s*:([^;{}]+);", body)}


def _static_references(page: str) -> list[str]:
    """Every path the page asks the static pipeline for, relative to ``STATIC_URL``."""
    prefix = re.escape(str(settings.STATIC_URL))
    return re.findall(rf'["\']{prefix}([^"\']+)["\']', page)


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
    """B16: the pipeline exists now, and the design system stays inline anyway (B14 shape kept)."""
    page = _page(client, "service-create")

    assert "<style" in page
    assert "<script" in page
    assert "<script src=" not in page
    assert 'rel="stylesheet"' not in page


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


def test_the_header_shows_the_company_lockup_for_each_theme(client: Client) -> None:
    """B16: the owner asked for the real logo, and it has to exist in both inks to swap."""
    page = _page(client, "service-list")

    assert "logo/vale-verde-light.svg" in page
    assert "logo/vale-verde-dark.svg" in page
    assert page.count('alt="Vale Verde Ambiental"') == 2


def test_the_header_names_the_product_and_never_repeats_the_company_beside_the_lockup(
    client: Client,
) -> None:
    """B16: the lockup already reads Vale Verde, so the words beside it are the product name."""
    page = _page(client, "service-list")

    assert "Controle de Serviços" in page
    assert "Prazos de serviços" not in page
    assert '<span class="brand__product">Vale Verde' not in page


def test_the_placeholder_leaf_mark_is_gone(client: Client) -> None:
    """B16: the header carried a drawn leaf standing in for an identity the company already has."""
    page = _page(client, "service-list")

    assert "brand__mark" not in page


def test_every_static_file_the_page_asks_for_is_one_the_pipeline_can_find(client: Client) -> None:
    """B16: a referenced asset that no finder resolves is a 404 on the page and nothing else."""
    references = _static_references(_page(client, "service-list"))

    assert references
    for reference in references:
        assert finders.find(reference) is not None, reference


def test_the_administration_site_assets_are_collectable(client: Client) -> None:
    """B16: the administration site is the maintenance door of foundation section 6, unstyled

    until its own bundle is served. The pipeline that finds this file is the one that serves it.
    """
    assert finders.find("admin/css/base.css") is not None
    assert finders.find("admin/css/dark_mode.css") is not None


def test_static_files_are_served_inside_the_secret_path_segment(client: Client) -> None:
    """Foundation section 6: the health endpoint is the single route outside the segment."""
    page = _page(client, "service-list")
    segment = settings.DEADLINER.secret_path_segment

    assert str(settings.STATIC_URL) == f"/{segment}/static/"
    for reference in _static_references(page):
        assert f"/{segment}/static/{reference}" in page


def test_every_screen_asks_the_browser_for_its_icon(client: Client) -> None:
    """B16: a tab with no icon is the tab an employee loses among fifteen others."""
    page = _page(client, "service-list")

    assert 'rel="icon"' in page
    assert "favicon.ico" in page


def test_the_theme_control_offers_the_three_states_in_portuguese(client: Client) -> None:
    """B16: follow the system, force light, force dark, named in the language of the interface."""
    page = _page(client, "service-list")

    assert 'role="radiogroup"' in page
    assert ">Tema<" in page
    for label in ("Sistema", "Claro", "Escuro"):
        assert f">{label}<" in page
    for value in ("system", "light", "dark"):
        assert f'type="radio" name="theme" value="{value}"' in page


def test_the_theme_control_is_a_real_keyboard_operable_control(client: Client) -> None:
    """B16: three radios in one group give arrow keys and a name for free; a div gives neither."""
    page = _page(client, "service-list")

    assert page.count('class="theme__input" type="radio"') == 3
    assert 'aria-labelledby="tema-titulo"' in page
    assert 'id="tema-titulo"' in page


def test_the_theme_defaults_to_the_operating_system_setting(client: Client) -> None:
    """B16: the owner asked for the device to decide until somebody says otherwise."""
    page = _page(client, "service-list")

    assert 'value="system" checked' in page
    assert '<html lang="pt-BR">' in page
    assert "prefers-color-scheme: dark" in page


def test_the_stored_theme_is_applied_before_the_page_is_painted(client: Client) -> None:
    """B16: a choice applied by the deferred bundle is a flash of the theme nobody asked for."""
    page = _page(client, "service-list")
    head = page[: page.index("</head>")]

    assert "vv-theme" in head
    assert "data-theme" in head
    assert "<script defer" not in head
    assert "<script async" not in head


def test_the_theme_is_remembered_under_a_single_storage_key(client: Client) -> None:
    """B16: two scripts reading two keys is a control that forgets what it just stored."""
    page = _page(client, "service-list")

    arguments = set(re.findall(r"localStorage\.\w+\(([^,)]*)", page))

    assert arguments == {"STORAGE_KEY"}
    assert page.count('STORAGE_KEY = "vv-theme"') == 1


def test_a_browser_refusing_storage_still_renders(client: Client) -> None:
    """B16: private windows and blocked site data throw on the first read, before any paint."""
    page = _page(client, "service-list")

    assert "try {" in page
    assert "catch (error)" in page


def test_the_tokens_resolve_in_each_of_the_three_theme_states(client: Client) -> None:
    """B16: a manual override has to beat the media query in both directions, not just one."""
    page = _page(client, "service-list")

    assert ':root:not([data-theme="light"])' in page
    assert ':root[data-theme="dark"]' in page
    assert ':root[data-theme="light"]' in page
    assert "color-scheme: light dark" in page


def test_the_two_dark_theme_blocks_declare_the_same_tokens(client: Client) -> None:
    """B16: the system default and the manual override read two rules that must not drift."""
    page = _page(client, "service-list")

    by_system = _declarations(_rule_body(page, ':root:not([data-theme="light"])', "--sage-1"))
    by_choice = _declarations(_rule_body(page, ':root[data-theme="dark"]', "--sage-1"))

    assert by_system == by_choice
    assert by_system["--canvas"] == "var(--sage-1)"


def test_the_lockup_swaps_with_the_theme_in_every_state(client: Client) -> None:
    """B16: a picture element follows the system and ignores a manual choice, so CSS does it."""
    page = _page(client, "service-list")

    assert ':root:not([data-theme="light"]) .brand__logo--dark' in page
    assert ':root[data-theme="dark"] .brand__logo--dark' in page
    assert ':root[data-theme="dark"] .brand__logo--light' in page


def test_the_registration_column_is_centred(client: Client) -> None:
    """B16: the owner reported the form pinned to the left of a wide page."""
    page = _page(client, "service-create")

    assert 'class="shell shell--narrow"' in page
    assert "margin: 0 auto" in _rule_body(page, "\n  .shell {", "max-width")
    assert "max-width" in _rule_body(page, ".shell--narrow", "max-width")


def test_the_list_screen_keeps_the_full_width_the_form_gives_up(client: Client) -> None:
    """B16: five columns and a narrow column of fields want different widths."""
    page = _page(client, "service-list")

    assert 'class="shell"' in page
    assert 'class="shell shell--narrow"' not in page


def test_the_focus_ring_is_drawn_in_a_step_that_carries_against_both_pages(
    client: Client,
) -> None:
    """B16: the ring B14 chose measures 2.27:1 in the light theme, under the 3:1 a ring needs.

    Measured ratios for every pair are in specs/dependencies.md, B16 section.
    """
    page = _page(client, "service-list")

    assert "--focus-ring: var(--green-11)" in page
