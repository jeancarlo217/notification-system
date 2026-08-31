"""B24, the date field is typed, and typing it should not be a chore.

Trace: foundation section 3.3 (the start date is one of the two facts the schedule derives from),
section 12, and the accessibility standard B14 and B16 hold this interface to.

B23 removed the native date input because the browser drew it in the browser's own locale and a
date typed day first was read month first. What replaced it was a bare text field whose only
statement of the format was a placeholder, which disappears at the first keystroke and is not
reliably announced. These tests are about the field being usable, not about the date being right,
which `tests/test_date_input.py` already covers.
"""

import re

import pytest
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db


def _page(name: str = "service-create") -> str:
    return Client().get(reverse(name)).content.decode()


def _start_date_input(page: str) -> str:
    found = re.search(r'<input[^>]*name="start_date"[^>]*>', page)
    assert found is not None
    return found.group(0)


def test_the_format_is_help_text_and_not_only_a_placeholder() -> None:
    """B24: a placeholder vanishes at the first keystroke, which is when the format is needed."""
    page = _page()

    assert "dia/mês/ano" in page


def test_the_help_text_is_associated_with_the_field_it_describes() -> None:
    """B24: unassociated help is help a screen reader never reads out with the control."""
    page = _page()

    assert 'aria-describedby="id_start_date_help"' in _start_date_input(page)
    assert 'id="id_start_date_help"' in page


def test_the_browser_refuses_a_date_that_is_not_one_before_the_round_trip() -> None:
    """B24: the server already refuses letters; this is about when the person finds out."""
    field = _start_date_input(_page())

    assert "pattern=" in field
    assert "title=" in field


def test_the_calendar_button_is_named_in_portuguese() -> None:
    """B24: an icon with no accessible name is a button nobody can reach without a mouse."""
    page = _page()

    assert "Escolher no calendário" in page


def test_the_calendar_is_hidden_until_the_script_can_drive_it() -> None:
    """B24: everything here is progressive, so a button that needs a script starts hidden."""
    page = _page()
    button = re.search(r"<button[^>]*data-dateinput-open[^>]*>", page)

    assert button is not None
    assert "hidden" in button.group(0)


def test_the_picker_never_posts_anything_of_its_own() -> None:
    """B24: the native input exists to drive a calendar, and a nameless input is not submitted."""
    page = _page()
    native = re.search(r"<input[^>]*data-dateinput-native[^>]*>", page)

    assert native is not None
    assert "name=" not in native.group(0)
