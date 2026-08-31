"""Browsing the list: the search box and the pages (backlog B17).

Traces: foundation section 1 (the employees reach their records through one list), section 8 (the
listing reads in a constant number of queries, whatever the dataset holds) and section 12 (the
interface is in Portuguese).

The page size is imported rather than repeated, so changing it edits one place and these tests
keep describing behaviour instead of a number.
"""

import datetime
import re
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

import pytest
from django.test import Client
from django.urls import reverse

from core.views import SERVICES_PER_PAGE
from tests.builders import a_catalog_service, a_service

pytestmark = pytest.mark.django_db

QueryCounter = Callable[..., AbstractContextManager[Any]]

_ROW = re.compile(r'data-label="Cliente">([^<]*)<')


def _clients_on(client: Client, **query: str | int) -> list[str]:
    """The client names the list renders, in the order the page prints them."""
    response = client.get(reverse("service-list"), query)
    return _ROW.findall(response.content.decode())


def _services_named(count: int) -> None:
    """``count`` records, each due a day later than the one before, so the order is unambiguous."""
    for number in range(count):
        a_service(
            client=f"Cliente {number:03d}",
            due_date=datetime.date(2027, 1, 1) + datetime.timedelta(days=number),
        )


def test_the_list_shows_one_page_of_records_and_not_the_whole_table() -> None:
    """B17: a list that prints every row grows without bound and stops being readable."""
    _services_named(SERVICES_PER_PAGE + 5)

    assert len(_clients_on(Client())) == SERVICES_PER_PAGE


def test_the_second_page_shows_what_the_first_one_left_out() -> None:
    """B17: paging is only useful if the records past the first page are reachable."""
    _services_named(SERVICES_PER_PAGE + 5)
    browser = Client()

    first, second = _clients_on(browser), _clients_on(browser, page=2)

    assert len(second) == 5
    assert set(first).isdisjoint(second)


def test_the_pages_keep_the_due_date_order_across_the_boundary() -> None:
    """B17: the nearest deadline is the reason the list exists, so page one carries the nearest."""
    _services_named(SERVICES_PER_PAGE + 5)
    browser = Client()

    first, second = _clients_on(browser), _clients_on(browser, page=2)

    assert first == sorted(first)
    assert max(first) < min(second)


def test_a_page_number_that_is_not_a_number_falls_back_to_the_first_page() -> None:
    """B17: a hand edited or truncated link shows the list, never an error screen."""
    _services_named(SERVICES_PER_PAGE + 5)

    assert _clients_on(Client(), page="banana") == _clients_on(Client())


def test_a_page_number_past_the_end_falls_back_to_the_last_page() -> None:
    """B17: a stale bookmark from a shorter dataset still lands on records."""
    _services_named(SERVICES_PER_PAGE + 5)
    browser = Client()

    assert _clients_on(browser, page=99) == _clients_on(browser, page=2)


def test_searching_a_client_name_narrows_the_list_to_that_client() -> None:
    """B17: the search box answers the question the employees actually ask, which client is this."""
    a_service(client="Fazenda Boa Vista")
    a_service(client="Sitio Sao Jorge")

    assert _clients_on(Client(), q="Boa Vista") == ["Fazenda Boa Vista"]


def test_searching_a_service_name_narrows_the_list_to_that_service() -> None:
    """B17: what a record is comes from the catalogue (ADR 0005), so the catalogue name is
    searchable too."""
    outorga = a_catalog_service(name="Outorga de Recursos Hidricos", position=2)
    a_service(client="Fazenda Boa Vista")
    a_service(client="Sitio Sao Jorge", catalog_service=outorga)

    assert _clients_on(Client(), q="Outorga") == ["Sitio Sao Jorge"]


def test_the_search_ignores_letter_case() -> None:
    """B17: nobody types a client name the way it was registered."""
    a_service(client="Fazenda Boa Vista")

    assert _clients_on(Client(), q="fazenda boa vista") == ["Fazenda Boa Vista"]


def test_the_search_ignores_surrounding_blanks() -> None:
    """B17: a term pasted from somewhere else carries the blanks of wherever it came from."""
    a_service(client="Fazenda Boa Vista")

    assert _clients_on(Client(), q="  Boa Vista  ") == ["Fazenda Boa Vista"]


def test_an_empty_search_shows_everything_again() -> None:
    """B17: clearing the box is how the employee goes back to the whole list."""
    _services_named(3)

    assert len(_clients_on(Client(), q="")) == 3


def test_a_search_matching_nothing_says_so_and_keeps_the_box_usable() -> None:
    """B17: an empty result explains itself, and never reads as an empty database."""
    a_service(client="Fazenda Boa Vista")

    page = Client().get(reverse("service-list"), {"q": "Nao existe"}).content.decode()

    assert "Nenhum serviço encontrado" in page
    assert 'value="Nao existe"' in page


def test_the_page_links_carry_the_search_term() -> None:
    """B17: paging inside a search that silently drops the term shows the wrong records."""
    _services_named(SERVICES_PER_PAGE + 5)

    page = Client().get(reverse("service-list"), {"q": "Cliente"}).content.decode()

    assert "q=Cliente&amp;page=2" in page or "page=2&amp;q=Cliente" in page


def test_a_searched_page_costs_the_same_queries_as_an_unsearched_one(
    django_assert_max_num_queries: QueryCounter,
    django_assert_num_queries: QueryCounter,
) -> None:
    """Foundation section 8: neither the filter nor the paging may add a query per row."""
    _services_named(1)
    browser = Client()

    with django_assert_max_num_queries(10) as one_record:
        browser.get(reverse("service-list"), {"q": "Cliente"})

    _services_named(SERVICES_PER_PAGE + 5)

    with django_assert_num_queries(len(one_record.captured_queries)):
        browser.get(reverse("service-list"), {"q": "Cliente"})
