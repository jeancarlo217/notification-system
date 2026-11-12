"""B21, the interface has to be usable on the screen the employee is holding.

Trace: foundation section 1, whose audience is the employees of one company reached through a
link, on whatever device they open it with. The defect this item repairs is specific: the list
answered the seven columns of B15 with a sideways scrollbar (six since B27 removed the
warning chips), which put the actions column off
screen on a tablet, so completing a service was unreachable without scrolling the table itself.
"""

import pytest
from django.test import Client
from django.urls import reverse

from tests.builders import a_service

pytestmark = pytest.mark.django_db


def _page(name: str = "service-list") -> str:
    return Client().get(reverse(name)).content.decode()


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

    for column in ("Cliente", "Serviço", "Vencimento", "Responsável", "Status", "Ações"):
        assert f'data-label="{column}"' in page


def test_every_cell_of_the_list_is_addressable_by_the_layout() -> None:
    """B21: the card layout places cells by name, so a cell with no class cannot be placed."""
    a_service()

    page = _page()

    for cell in ("client", "service", "date", "submitter", "status", "actions"):
        assert f'class="table__{cell}"' in page


def test_the_state_of_the_days_list_is_one_block_above_the_records_and_not_a_column() -> None:
    """B27: the per threshold chips of B15 have nothing left to show, so the list is six columns
    and the state of today's list is said once, above them, where no width can push it off
    screen."""
    a_service()

    page = _page()

    assert 'data-label="Avisos"' not in page
    assert "table__warnings" not in page
    assert page.index('class="dispatch') < page.index('<table class="table"')


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
