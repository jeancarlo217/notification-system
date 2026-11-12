"""B8, the Evolution adapter: the one real implementation of the provider interface.

Traces: foundation section 4 (deliver this text to the configured destination and say whether it
was accepted), I2 (every vendor failure is answered ``False`` and never raised, so the engine
records a visible failed state), I5 (the API key reaches no log line), and the findings of
``specs/dependencies.md`` for the pinned 2.3.7: ``POST /message/sendText/{instance}`` with the
``apikey`` header and a top level ``number`` and ``text``, answered with ``key.id``.

Two layers. The request and the reading of the answer are pure and tested as values. The
transport is exercised against a gateway stood up on the loopback address by this file, which is
neither the vendor nor a mock of the HTTP client: it is a real socket answering what the test
scripted, so a timeout and a refused connection are observed and not imagined. One test speaks to
a real instance and runs only when asked to, because it puts a message in a real group.
"""

import json
import logging
import os
import socket
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.test import override_settings

from core.evolution import EvolutionProvider, send_text_request, was_accepted
from core.models import Dispatch
from core.provider import get_provider
from deadliner.config import EvolutionConfig, get_evolution_config
from tests.builders import a_service
from tests.configuration import TEST_DEADLINER

GROUP = "120363000000000000@g.us"
API_KEY = "placeholder-key-for-tests-only"
ACCEPTED = (
    b'{"key": {"remoteJid": "x@g.us", "fromMe": true, "id": "3EB0C5A2"}, "status": "PENDING"}'
)

GATEWAY = EvolutionConfig(
    base_url="http://evolution:8080", instance_name="valeverde", api_key=API_KEY
)


@dataclass
class ScriptedGateway:
    """A gateway on the loopback address that answers what a test told it to."""

    status: int = 201
    body: bytes = ACCEPTED
    hold: threading.Event | None = None
    received: list[dict[str, object]] = field(default_factory=list)
    base_url: str = ""

    def config(self) -> EvolutionConfig:
        return EvolutionConfig(base_url=self.base_url, instance_name="valeverde", api_key=API_KEY)


@pytest.fixture
def gateway() -> Iterator[ScriptedGateway]:
    scripted = ScriptedGateway()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            scripted.received.append(
                {
                    "path": self.path,
                    "apikey": self.headers.get("apikey"),
                    "content_type": self.headers.get("Content-Type"),
                    "body": json.loads(self.rfile.read(length)),
                }
            )
            if scripted.hold is not None:
                scripted.hold.wait()
            self.send_response(scripted.status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(scripted.body)))
            self.end_headers()
            self.wfile.write(scripted.body)

        def log_message(self, format: str, *args: object) -> None:
            return None

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    scripted.base_url = f"http://127.0.0.1:{server.server_address[1]}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield scripted
    finally:
        if scripted.hold is not None:
            scripted.hold.set()
        server.shutdown()
        server.server_close()


def _a_closed_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port: int = probe.getsockname()[1]
    return port


def test_the_request_goes_to_the_send_text_call_of_the_configured_instance() -> None:
    """B8, dependencies: the instance name is the last segment of the call."""
    request = send_text_request(GATEWAY, GROUP, "texto")

    assert request.url == "http://evolution:8080/message/sendText/valeverde"


def test_the_request_carries_the_destination_and_the_text_at_the_top_level() -> None:
    """B8, the trap of 2026-08-28: 2.3.7 takes a top level `text`, never the `textMessage.text`
    its own documentation page still shows, and the destination verbatim in `number`."""
    request = send_text_request(GATEWAY, GROUP, "texto")

    assert json.loads(request.body) == {"number": GROUP, "text": "texto"}


def test_accents_and_line_breaks_survive_the_request_body() -> None:
    """Foundation section 4: the list is Portuguese and many lines long."""
    text = "Serviços em aberto\n• *Sítio Santa Fé* | venceu há 3 dias"

    request = send_text_request(GATEWAY, GROUP, text)

    assert json.loads(request.body.decode("utf-8"))["text"] == text


def test_the_request_presents_the_api_key_and_declares_json() -> None:
    """B8, dependencies: the `apikey` header is what every gateway call is authenticated by."""
    request = send_text_request(GATEWAY, GROUP, "texto")

    assert request.headers == {"apikey": API_KEY, "Content-Type": "application/json"}


def test_an_answer_carrying_a_message_id_is_acceptance() -> None:
    """B8: acceptance is read from `key.id` in the body of a successful answer."""
    assert was_accepted(201, ACCEPTED) is True
    assert was_accepted(200, b'{"key": {"id": "3EB0"}}') is True


@pytest.mark.parametrize(
    "body",
    [
        b"",
        b"not json",
        b"[]",
        b"null",
        b'"3EB0"',
        b"{}",
        b'{"key": null}',
        b'{"key": "3EB0"}',
        b'{"key": {}}',
        b'{"key": {"id": ""}}',
        b'{"key": {"id": null}}',
        b'{"status": "PENDING"}',
        b"\xff\xfe",
    ],
)
def test_a_successful_status_with_no_message_id_is_not_acceptance(body: bytes) -> None:
    """I2: a 201 that names no message proves nothing was queued, so it is a failure."""
    assert was_accepted(201, body) is False


@pytest.mark.parametrize("status", [301, 400, 401, 403, 404, 500, 502])
def test_an_unsuccessful_status_is_not_acceptance_whatever_the_body_says(status: int) -> None:
    """I2: only a successful answer can accept a message."""
    assert was_accepted(status, ACCEPTED) is False


def test_an_accepted_send_reports_true_and_the_gateway_received_it(
    gateway: ScriptedGateway,
) -> None:
    """Foundation section 4: deliver the text to the destination and say it was accepted."""
    provider = EvolutionProvider(gateway.config(), GROUP)

    accepted = provider.deliver("Serviços em aberto")

    assert accepted is True
    assert gateway.received == [
        {
            "path": "/message/sendText/valeverde",
            "apikey": API_KEY,
            "content_type": "application/json",
            "body": {"number": GROUP, "text": "Serviços em aberto"},
        }
    ]


@pytest.mark.parametrize("status", [400, 401, 404, 500])
def test_a_refusal_from_the_gateway_reports_false_and_raises_nothing(
    gateway: ScriptedGateway, status: int
) -> None:
    """I2: every vendor failure is mapped to False, never raised."""
    gateway.status = status
    gateway.body = b'{"status": 400, "error": "Bad Request"}'

    assert EvolutionProvider(gateway.config(), GROUP).deliver("texto") is False


def test_an_answer_that_is_not_the_expected_json_reports_false(gateway: ScriptedGateway) -> None:
    """I2: a proxy page or a truncated body in place of the answer is a failure."""
    gateway.body = b"<html>502 Bad Gateway</html>"

    assert EvolutionProvider(gateway.config(), GROUP).deliver("texto") is False


def test_a_gateway_that_is_not_listening_reports_false_and_raises_nothing() -> None:
    """I2: the Evolution container being down is the ordinary failure, and it is not a crash."""
    down = EvolutionConfig(
        base_url=f"http://127.0.0.1:{_a_closed_port()}", instance_name="valeverde", api_key=API_KEY
    )

    assert EvolutionProvider(down, GROUP).deliver("texto") is False


def test_a_gateway_that_does_not_answer_in_time_reports_false(gateway: ScriptedGateway) -> None:
    """B8: every call has a timeout, so a hung gateway cannot hang the daily run."""
    gateway.hold = threading.Event()
    provider = EvolutionProvider(gateway.config(), GROUP, timeout=0.2)

    assert provider.deliver("texto") is False


def test_the_api_key_never_reaches_a_log_line(
    gateway: ScriptedGateway, caplog: pytest.LogCaptureFixture
) -> None:
    """I5: a failed send is logged, and the credential is in none of what is logged."""
    gateway.status = 401
    down = EvolutionConfig(
        base_url=f"http://127.0.0.1:{_a_closed_port()}", instance_name="valeverde", api_key=API_KEY
    )

    with caplog.at_level(logging.DEBUG):
        EvolutionProvider(gateway.config(), GROUP).deliver("texto")
        EvolutionProvider(down, GROUP).deliver("texto")

    logged = " ".join(f"{record.getMessage()} {record.__dict__}" for record in caplog.records)
    assert caplog.records
    assert API_KEY not in logged


def test_a_failed_send_is_logged_with_its_reason(
    gateway: ScriptedGateway, caplog: pytest.LogCaptureFixture
) -> None:
    """I2: the failure is visible to whoever reads the container log, with what the gateway
    answered."""
    gateway.status = 500

    with caplog.at_level(logging.WARNING):
        EvolutionProvider(gateway.config(), GROUP).deliver("texto")

    failures = [
        record for record in caplog.records if record.__dict__.get("event") == "gateway_send"
    ]
    assert failures[0].__dict__["http_status"] == 500


def test_the_factory_refuses_where_no_gateway_is_configured() -> None:
    """I2, B26: phase one has no gateway, and resolving a provider there fails loudly, never as
    a silent no-op."""
    with override_settings(EVOLUTION=None), pytest.raises(ImproperlyConfigured):
        get_provider()


def test_the_factory_returns_the_adapter_bound_to_the_configured_destination(
    gateway: ScriptedGateway,
) -> None:
    """B8, I4: the provider the daily run resolves sends to the one configured destination."""
    configured = override_settings(EVOLUTION=gateway.config(), DEADLINER=TEST_DEADLINER)

    with configured:
        accepted = get_provider().deliver("texto")

    assert accepted is True
    assert gateway.received[0]["body"] == {"number": "5567999998888", "text": "texto"}


@pytest.mark.django_db
def test_the_daily_command_delivers_the_list_through_the_real_adapter(
    gateway: ScriptedGateway,
) -> None:
    """Foundation sections 4 and 5 end to end: the command, the engine and the adapter, with
    only the gateway stood in for."""
    a_service(client="Fazenda Boa Vista")

    with override_settings(EVOLUTION=gateway.config(), DEADLINER=TEST_DEADLINER):
        call_command("send_alerts", now="2026-12-18T07:00")

    assert Dispatch.objects.get().state == "sent"
    assert gateway.received[0]["body"] == {
        "number": "5567999998888",
        "text": "2026-12-18|1\nFazenda Boa Vista|Licenciamentos Ambientais|2026-12-25|in 7",
    }


@pytest.mark.django_db
def test_the_daily_command_records_a_failed_list_when_the_gateway_refuses(
    gateway: ScriptedGateway,
) -> None:
    """I2 end to end: a refusal from the gateway is the day's list in the failed state."""
    gateway.status = 500
    a_service(client="Fazenda Boa Vista")

    with override_settings(EVOLUTION=gateway.config(), DEADLINER=TEST_DEADLINER):
        call_command("send_alerts", now="2026-12-18T07:00")

    assert Dispatch.objects.get().state == "failed"


@pytest.mark.skipif(
    os.environ.get("EVOLUTION_LIVE_SEND") != "1" or get_evolution_config() is None,
    reason="puts a real message in the configured destination; set EVOLUTION_LIVE_SEND=1 to run",
)
def test_a_real_instance_accepts_a_message() -> None:
    """specs/testing.md: the few integration tests prove the seam speaks to the real thing."""
    assert get_provider().deliver("Teste de integração do adaptador (B8).") is True
