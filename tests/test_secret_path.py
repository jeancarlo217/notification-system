"""B5, secret path access and health endpoint.

Traces: foundation section 6 (the whole application is served under a secret path segment held in
configuration, a health endpoint is the single route outside it and touches no dependency, and
Django's administration site sits inside the segment keeping the framework's authentication) and
I7 (the segment is redacted on the logging path before any log line is written).
"""

import io
import logging
from typing import Any

import pytest
from django.test import Client
from django.urls import reverse

from deadliner.config import get_config


def _segment() -> str:
    """The configured secret segment, read from the boundary so no literal enters the repository."""
    return get_config().secret_path_segment


def _capture_every_configured_stream(monkeypatch: pytest.MonkeyPatch) -> io.StringIO:
    """Point every stream this project logs through at memory, and let every record reach it.

    I7 is about what actually gets written, so the assertions read the configured handlers rather
    than a capture fixture the application knows nothing about.
    """
    stream = io.StringIO()
    loggers: list[logging.Logger] = [logging.getLogger()]
    loggers += [
        existing
        for existing in logging.root.manager.loggerDict.values()
        if isinstance(existing, logging.Logger)
    ]
    handlers: list[logging.StreamHandler[Any]] = [
        handler
        for logger in loggers
        for handler in logger.handlers
        if isinstance(handler, logging.StreamHandler)
    ]
    assert handlers, "the project configures no stream handler, so I7 cannot be observed"
    for handler in handlers:
        monkeypatch.setattr(handler, "stream", stream)
        monkeypatch.setattr(handler, "level", logging.DEBUG)
    monkeypatch.setattr(logging.getLogger(), "level", logging.DEBUG)
    return stream


@pytest.mark.django_db
def test_the_application_is_served_under_the_configured_secret_segment(client: Client) -> None:
    """Foundation section 6: the employee reaches the list only through the secret link."""
    listing = reverse("service-list")

    assert listing.startswith(f"/{_segment()}/")
    assert client.get(listing).status_code == 200


def test_the_site_root_offers_nothing(client: Client) -> None:
    """Foundation section 6: without the link there is no application to find at the root."""
    assert client.get("/").status_code == 404


def test_a_wrong_segment_reaches_no_screen(client: Client) -> None:
    """Foundation section 6: the segment is the credential, so a near miss is simply not found."""
    assert client.get("/servicos/").status_code == 404


def test_the_health_endpoint_answers_outside_the_secret_segment(client: Client) -> None:
    """Foundation section 6: the container runtime probes one route and holds no credential."""
    health = reverse("health")

    assert _segment() not in health
    assert client.get(health).status_code == 200


@pytest.mark.django_db
def test_the_health_endpoint_touches_no_dependency(
    client: Client,
    django_assert_num_queries: Any,
) -> None:
    """Foundation section 6: liveness reports the process is up, never that SQLite answered."""
    with django_assert_num_queries(0):
        client.get(reverse("health"))


def test_the_administration_site_lives_inside_the_secret_segment(client: Client) -> None:
    """Foundation section 6: the maintenance door sits behind the link as well as a password."""
    assert reverse("admin:index").startswith(f"/{_segment()}/")


def test_the_administration_site_is_not_reachable_at_the_site_root(client: Client) -> None:
    """Foundation section 6: the framework's default admin path is not a second way in."""
    assert client.get("/admin/").status_code == 404


@pytest.mark.django_db
def test_the_administration_site_keeps_asking_who_you_are(client: Client) -> None:
    """Foundation section 6: two barriers guard that door, the link and the standard login."""
    response = client.get(reverse("admin:index"))

    assert response.status_code == 302
    assert "/login/" in response.headers["Location"]


def test_the_secret_segment_never_reaches_the_log_stream(
    client: Client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """I7: a request that Django logs by path leaves the segment out of every written line."""
    stream = _capture_every_configured_stream(monkeypatch)

    client.get(f"/{_segment()}/rota-inexistente/")

    assert _segment() not in stream.getvalue()


def test_the_redacted_line_still_reports_which_path_was_requested(
    client: Client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """I7: redaction hides the credential and keeps the log useful, it does not drop the line."""
    stream = _capture_every_configured_stream(monkeypatch)

    client.get(f"/{_segment()}/rota-inexistente/")

    assert "rota-inexistente" in stream.getvalue()


def test_the_segment_is_redacted_whichever_logger_carries_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """I7: redaction sits on the logging path itself, not on one well behaved caller."""
    stream = _capture_every_configured_stream(monkeypatch)

    logging.getLogger("core").warning("caminho %s", f"/{_segment()}/servicos/novo/")

    assert _segment() not in stream.getvalue()
    assert "/servicos/novo/" in stream.getvalue()


def test_a_line_carrying_no_segment_is_written_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """I7: the filter redacts the credential and leaves every other message alone."""
    stream = _capture_every_configured_stream(monkeypatch)

    logging.getLogger("core").warning("alerta %s enviado", 42)

    assert "alerta 42 enviado" in stream.getvalue()


def test_the_request_line_the_development_server_writes_carries_no_segment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """I7: runserver logs every request by path through its own logger, which is a log line too."""
    stream = _capture_every_configured_stream(monkeypatch)

    logging.getLogger("django.server").info('"GET /%s/ HTTP/1.1" 200 512', _segment())

    assert _segment() not in stream.getvalue()
    assert "GET" in stream.getvalue()
