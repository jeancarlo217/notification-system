"""B13, the normalization rule: ``normalize_person_name`` as a pure decision.

Traces: I8 (two submissions naming the same person resolve to one submitter record, however that
name is spelled in case, accent or spacing) and ADR 0006, which makes the rule a pure function so
it is reachable with plain data in and plain data out (specs/testing.md).

Nothing here touches the database or Django: this module is the whole of I8's logic, and the rows
it decides about live in ``tests/test_submitter.py``.
"""

import pytest

from core.identity import normalize_person_name


def test_the_normalized_form_of_a_name_folds_accents_case_and_spacing() -> None:
    """I8: the three differences the owner named collapse into one key, and nothing else does."""
    assert normalize_person_name("José  VICTOR ") == "jose victor"


def test_a_name_written_with_and_without_accents_is_the_same_person() -> None:
    """I8: José Victor and Jose Victor are one employee, so their keys agree."""
    assert normalize_person_name("José Victor") == normalize_person_name("Jose Victor")


def test_a_name_written_in_any_case_is_the_same_person() -> None:
    """I8: JOSÉ VICTOR typed in a hurry is not a second employee."""
    assert normalize_person_name("JOSÉ VICTOR") == normalize_person_name("josé victor")


def test_a_cedilla_folds_like_any_other_mark() -> None:
    """I8: the rule folds combining marks, so it is not a table of the accents somebody listed."""
    assert normalize_person_name("Conceição") == normalize_person_name("Conceicao")


def test_leading_and_trailing_whitespace_does_not_make_a_second_person() -> None:
    """I8: a trailing space from a paste is invisible on screen and must be invisible here."""
    assert normalize_person_name("  José Victor  ") == normalize_person_name("José Victor")


def test_repeated_whitespace_inside_a_name_collapses() -> None:
    """I8 acceptance uses jose  victor with two spaces; it is the same person as with one."""
    assert normalize_person_name("jose  victor") == normalize_person_name("jose victor")


@pytest.mark.parametrize("raw", ["José\tVictor", "José\nVictor", "José \t Victor"])
def test_a_tab_or_a_newline_counts_as_whitespace(raw: str) -> None:
    """I8: whitespace is whatever the keyboard produced, not the space character alone."""
    assert normalize_person_name(raw) == "jose victor"


@pytest.mark.parametrize("raw", ["", "   ", "\t\n  "])
def test_a_name_that_is_only_whitespace_normalizes_to_empty(raw: str) -> None:
    """I8: an empty key is the signal the form turns into a validation error, never a row."""
    assert normalize_person_name(raw) == ""


def test_punctuation_is_significant_so_a_trailing_dot_is_another_person() -> None:
    """ADR 0006, a deliberate non-goal: the rule does not strip punctuation, and widening it
    would eventually merge two real people who share a first name."""
    assert normalize_person_name("José Victor.") != normalize_person_name("José Victor")


def test_abbreviation_is_significant_so_an_initial_is_another_person() -> None:
    """ADR 0006, a deliberate non-goal: the rule reconciles no nickname, initial or surname."""
    assert normalize_person_name("José V.") != normalize_person_name("José Victor")


def test_normalizing_an_already_normalized_name_changes_nothing() -> None:
    """I8: the key is stable, so a stored key resolves to itself and never drifts on re-entry."""
    once = normalize_person_name("José  Victor")

    assert normalize_person_name(once) == once


def test_two_different_people_keep_two_different_keys() -> None:
    """I8, the quiet side: the rule collapses spellings of one name, never two names."""
    assert normalize_person_name("José Victor") != normalize_person_name("Geovanna")
