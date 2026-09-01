"""B21, the interface has to be usable on the screen the employee is holding.

Trace: foundation section 1, whose audience is the employees of one company reached through a
link, on whatever device they open it with. The defect this item repairs is specific: the list
answered the seven columns of B15 with a sideways scrollbar, which put the actions column off
screen on a tablet, so completing a service was unreachable without scrolling the table itself.
"""

import re

import pytest
from django.test import Client
from django.urls import reverse

from tests.builders import a_service

pytestmark = pytest.mark.django_db

_WARNINGS_CELL = re.compile(r'data-label="Avisos">(.*?)</td>', re.DOTALL)


def _page(name: str = "service-list") -> str:
    return Client().get(reverse(name)).content.decode()


def _warnings_cell() -> str:
    page = _page()
    found = _WARNINGS_CELL.search(page)
    assert found is not None
    return found.group(1)


def test_nothing_in_the_list_is_reached_by_scrolling_sideways() -> None:
    """B21: a table wider than its card hides the actions column behind a scrollbar."""
    a_service()

    page = _page()

    assert "card--scroll" not in page
    assert "overflow-x" not in page


def test_every_column_of_the_list_carries_its_name_for_the_card_layout() -> None:
    """B21: below the table width each cell is a labelled line, so each one states its column."""
    a_service()

    page = _page()

    for column in ("Cliente", "Serviço", "Vencimento", "Responsável", "Status", "Avisos", "Ações"):
        assert f'data-label="{column}"' in page


def test_every_cell_of_the_list_is_addressable_by_the_layout() -> None:
    """B21: the card layout places cells by name, so a cell with no class cannot be placed."""
    a_service()

    page = _page()

    for cell in ("client", "service", "date", "submitter", "status", "warnings", "actions"):
        assert f'class="table__{cell}"' in page


def test_a_warning_draws_its_state_and_never_only_prints_its_colour() -> None:
    """I2: a chip short enough to fit needs a shape, or the colour is the only channel left."""
    a_service()

    cell = _warnings_cell()

    assert cell.count("<li") == 3
    assert "warn--waiting" in cell


def test_a_failed_warning_keeps_its_word_where_an_eye_can_read_it() -> None:
    """I2: the state a person has to act on is the one that never hides behind an icon."""
    from core.models import Alert

    service = a_service()
    Alert.objects.create(service=service, threshold=30, state=Alert.State.FAILED)

    cell = _warnings_cell()
    failed = cell[cell.index("warn--failed") :]

    assert "falhou" in failed
    assert 'warn__word visually-hidden">falhou' not in failed


def test_a_warning_that_did_not_fail_still_says_its_state_to_a_reader_who_cannot_see() -> None:
    """I2: the word is in the markup for every state, drawn or not."""
    a_service()

    cell = _warnings_cell()

    assert cell.count('class="warn__word visually-hidden">aguardando') == 3


def test_the_two_halves_of_the_deadline_sit_where_the_layout_can_pair_them() -> None:
    """B21: the start date and the term decide one number together (foundation section 3.3)."""
    page = _page("service-create")

    assert 'class="field field--start_date"' in page
    assert 'class="field field--term_days"' in page


def test_the_edit_screen_is_laid_out_by_the_same_grid_as_the_registration() -> None:
    """B25: the edit screen writes the same five fields, so it is placed by the same rules.

    The grid puts a cell where its class says, so a field arriving without one falls into the
    next free column and the pair of foundation section 3.3 stops sitting on one row.
    """
    service = a_service()

    page = Client().get(reverse("service-edit", args=[service.pk])).content.decode()

    for field in ("client", "catalog_service", "notes", "start_date", "term_days"):
        assert f'class="field field--{field}"' in page


def test_the_observation_box_opens_at_the_height_the_row_can_afford() -> None:
    """B25: six empty rows under a five field form is scrolling bought with nothing.

    The script grows the box as it is typed into and an edit arrives already grown to its text,
    so the attribute is the floor and never the ceiling.
    """
    assert 'rows="3"' in _page("service-create")
