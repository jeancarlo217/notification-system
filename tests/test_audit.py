"""B6, audit and structured logging.

Traces: foundation section 6 and I6 (every form submission produces a structured entry with the
submitter's IP, the country Cloudflare reports, the timestamp, the identifier of the record
touched and the submitter it belongs to, with the address taken from Cloudflare's forwarding
headers only), I8 (two submissions naming one person carry one submitter identifier) and the
observability rule of section 8 (logs are structured and carry their correlation keys, bound once
per request or run).
"""

import datetime
import json
import logging
from collections.abc import Iterator
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from django.core.management import call_command
from django.test import Client, override_settings
from django.urls import reverse

from core.identity import normalize_person_name
from core.models import Service, Submitter
from deadliner.config import DeadlinerConfig
from tests.builders import a_service, a_submitter, edit_payload, registration_payload
from tests.fakes import FakeProvider

pytestmark = pytest.mark.django_db

CLOUDFLARE_HEADERS = {"cf-connecting-ip": "203.0.113.7", "cf-ipcountry": "BR"}

TEST_DEADLINER = DeadlinerConfig(
    alert_thresholds=(30, 7, 0),
    whatsapp_destination="5567999998888",
    message_template="{client}|{service}|{due_date}|{days_remaining}",
    secret_path_segment="fake-segment-for-tests",
    timezone=ZoneInfo("America/Campo_Grande"),
)


class _Captured:
    """The lines this project actually wrote, as the structured entries they must be."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def write(self, text: str) -> int:
        self.lines.append(text)
        return len(text)

    def flush(self) -> None:
        return None

    def getvalue(self) -> str:
        # pytest's own capture handler reads its stream back at teardown, and this object stands
        # in for that stream too.
        return "".join(self.lines)

    def entries(self) -> list[dict[str, Any]]:
        parsed: list[dict[str, Any]] = []
        for line in self.getvalue().splitlines():
            try:
                candidate = json.loads(line)
            except ValueError:
                continue
            if isinstance(candidate, dict):
                parsed.append(candidate)
        return parsed

    def audit_entries(self) -> list[dict[str, Any]]:
        return [entry for entry in self.entries() if entry.get("event") == "service_submission"]


@pytest.fixture
def captured(monkeypatch: pytest.MonkeyPatch) -> Iterator[_Captured]:
    """Point every stream this project logs through at memory, and let every record reach it."""
    sink = _Captured()
    loggers: list[logging.Logger] = [logging.getLogger()]
    loggers += [
        existing
        for existing in logging.root.manager.loggerDict.values()
        if isinstance(existing, logging.Logger)
    ]
    for logger in loggers:
        for handler in logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                monkeypatch.setattr(handler, "stream", sink)
                monkeypatch.setattr(handler, "level", logging.DEBUG)
    monkeypatch.setattr(logging.getLogger(), "level", logging.DEBUG)
    yield sink


def _registered() -> Service:
    return a_service()


def test_a_registration_is_audited_with_address_country_timestamp_record_and_submitter(
    client: Client,
    captured: _Captured,
) -> None:
    """I6 acceptance: a POST carrying Cloudflare forwarding headers yields a log entry containing
    those five fields; with no login the entry is the only answer to who entered this."""
    client.post(reverse("service-create"), registration_payload(), headers=CLOUDFLARE_HEADERS)

    entry = captured.audit_entries()[0]
    stored = Service.objects.get()

    assert entry["client_ip"] == "203.0.113.7"
    assert entry["country"] == "BR"
    assert entry["service_id"] == stored.pk
    assert entry["submitter_id"] == stored.submitter_id
    assert datetime.datetime.fromisoformat(entry["timestamp"])


def test_two_spellings_of_one_name_carry_one_submitter_through_both_entries(
    client: Client,
    captured: _Captured,
) -> None:
    """I8 acceptance: submit once as José Victor and once as jose  victor; exactly one submitter
    row carries that name, the number of submitter rows is unchanged by the second submission,
    and both audit entries carry that row's identifier."""
    client.post(
        reverse("service-create"),
        registration_payload(submitter="José Victor"),
        headers=CLOUDFLARE_HEADERS,
    )
    after_first = Submitter.objects.count()

    client.post(
        reverse("service-create"),
        registration_payload(submitter="jose  victor"),
        headers=CLOUDFLARE_HEADERS,
    )

    resolved = Submitter.objects.filter(normalized_name=normalize_person_name("José Victor"))
    first, second = captured.audit_entries()

    assert resolved.count() == 1
    assert Submitter.objects.count() == after_first
    assert first["submitter_id"] == resolved.get().pk
    assert second["submitter_id"] == resolved.get().pk


def test_an_edit_is_audited_against_the_submitter_who_registered_the_record(
    client: Client,
    captured: _Captured,
) -> None:
    """ADR 0006: attribution is per record and not per edit, so the entry names who owns the
    record rather than who touched it that afternoon."""
    registrant = a_submitter("Marina Nogueira")
    service = a_service(submitter=registrant)

    client.post(
        reverse("service-edit", args=[service.pk]),
        edit_payload(start_date="2027-01-10"),
        headers=CLOUDFLARE_HEADERS,
    )

    assert captured.audit_entries()[0]["submitter_id"] == registrant.pk


def test_a_completion_is_audited_against_the_submitter_who_registered_the_record(
    client: Client,
    captured: _Captured,
) -> None:
    """ADR 0006: completing a service asks nobody for a name, and the entry it writes still
    carries the record's own submitter."""
    registrant = a_submitter("Marina Nogueira")
    service = a_service(submitter=registrant)

    client.post(reverse("service-complete", args=[service.pk]), headers=CLOUDFLARE_HEADERS)

    assert captured.audit_entries()[0]["submitter_id"] == registrant.pk


def test_a_due_date_edit_is_audited_against_the_record_it_touched(
    client: Client,
    captured: _Captured,
) -> None:
    """I6: every write is attributed, and an edit is a write."""
    service = _registered()

    client.post(
        reverse("service-edit", args=[service.pk]),
        edit_payload(start_date="2027-01-10"),
        headers=CLOUDFLARE_HEADERS,
    )

    entry = captured.audit_entries()[0]

    assert entry["service_id"] == service.pk
    assert entry["client_ip"] == "203.0.113.7"


def test_a_completion_is_audited_against_the_record_it_touched(
    client: Client,
    captured: _Captured,
) -> None:
    """I6: marking a service completed is a submission and is attributed like any other."""
    service = _registered()

    client.post(reverse("service-complete", args=[service.pk]), headers=CLOUDFLARE_HEADERS)

    entry = captured.audit_entries()[0]

    assert entry["service_id"] == service.pk


def test_a_refused_submission_writes_no_audit_entry(
    client: Client,
    captured: _Captured,
) -> None:
    """I6: the trail records writes that happened, so a rejected form is not one of them."""
    client.post(
        reverse("service-create"),
        registration_payload(client=""),
        headers=CLOUDFLARE_HEADERS,
    )

    assert captured.audit_entries() == []


def test_reading_the_list_writes_no_audit_entry(client: Client, captured: _Captured) -> None:
    """I6: the trail is about submissions, and reading a page is not one."""
    _registered()

    client.get(reverse("service-list"), headers=CLOUDFLARE_HEADERS)

    assert captured.audit_entries() == []


def test_the_audit_entry_is_one_structured_object_a_machine_can_read(
    client: Client,
    captured: _Captured,
) -> None:
    """Foundation section 8: logs are structured, so the trail is queryable and not prose."""
    client.post(reverse("service-create"), registration_payload(), headers=CLOUDFLARE_HEADERS)

    assert len(captured.audit_entries()) == 1


def test_the_address_is_never_invented_when_cloudflare_did_not_report_one(
    client: Client,
    captured: _Captured,
) -> None:
    """Foundation section 6: IP and country come from Cloudflare's headers only (OQ-2)."""
    client.post(reverse("service-create"), registration_payload(), REMOTE_ADDR="10.0.0.9")

    entry = captured.audit_entries()[0]

    assert entry["client_ip"] is None
    assert entry["country"] is None
    assert entry["service_id"] == Service.objects.get().pk


def test_every_request_is_logged_with_its_correlation_key_and_outcome(
    client: Client,
    captured: _Captured,
) -> None:
    """Foundation section 8: the line this application writes about a request carries its key."""
    client.get("/rota-inexistente/", headers=CLOUDFLARE_HEADERS)

    requests = [entry for entry in captured.entries() if entry.get("event") == "request"]

    assert requests[0]["request_id"]
    assert requests[0]["status"] == 404
    assert requests[0]["client_ip"] == "203.0.113.7"


def test_two_requests_are_told_apart_by_their_correlation_key(
    client: Client,
    captured: _Captured,
) -> None:
    """Foundation section 8: a correlation key that repeats correlates nothing."""
    client.post(reverse("service-create"), registration_payload(), headers=CLOUDFLARE_HEADERS)
    client.post(reverse("service-create"), registration_payload(), headers=CLOUDFLARE_HEADERS)

    first, second = captured.audit_entries()

    assert first["request_id"] != second["request_id"]


def test_the_request_context_does_not_leak_into_the_next_record(
    client: Client,
    captured: _Captured,
) -> None:
    """Foundation section 8: context bound for a request ends with it, or it lies afterwards."""
    client.post(reverse("service-create"), registration_payload(), headers=CLOUDFLARE_HEADERS)

    logging.getLogger("core").info("depois da requisicao")
    after = [
        entry for entry in captured.entries() if entry.get("message") == "depois da requisicao"
    ]

    assert after[0].get("client_ip") is None
    assert after[0].get("request_id") is None


@override_settings(DEADLINER=TEST_DEADLINER)
def test_a_daily_run_carries_its_own_correlation_keys(
    captured: _Captured,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Foundation section 8: a run binds its keys once, and each send names what it touched."""
    monkeypatch.setattr("core.provider.get_provider", lambda: FakeProvider())
    service = _registered()

    call_command("send_alerts", today="2026-12-25")

    sends = [entry for entry in captured.entries() if entry.get("event") == "alert_send"]

    assert sends[0]["run_id"]
    assert sends[0]["service_id"] == service.pk
    assert sends[0]["alert_id"]
