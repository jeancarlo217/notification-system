"""The Evolution API adapter behind the provider interface (backlog B8, foundation section 4).

One call of the vendor is used, ``POST /message/sendText/{instance}``, in the shape the source at
git tag 2.3.7 takes (specs/dependencies.md). The request and the reading of the answer are pure;
the transport is the standard library, by the owner decision of 2026-09-02.
"""

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from http import HTTPStatus

from deadliner.config import EvolutionConfig

_logger = logging.getLogger("core.evolution")

REQUEST_TIMEOUT_SECONDS = 15.0
"""How long one call may take before it is a failure; the engine retries within the hour."""


@dataclass(frozen=True, slots=True)
class GatewayRequest:
    """One HTTP call to the gateway, as plain data."""

    url: str
    headers: dict[str, str]
    body: bytes


def send_text_request(gateway: EvolutionConfig, destination: str, text: str) -> GatewayRequest:
    """The call that asks the gateway to deliver ``text`` to ``destination``."""
    return GatewayRequest(
        url=f"{gateway.base_url}/message/sendText/{gateway.instance_name}",
        headers={"apikey": gateway.api_key, "Content-Type": "application/json"},
        body=json.dumps({"number": destination, "text": text}).encode("utf-8"),
    )


def was_accepted(status: int, body: bytes) -> bool:
    """Whether an answer from the gateway says the message was taken.

    A successful status alone is not enough: acceptance is the message identifier in ``key.id``.
    """
    if not HTTPStatus.OK <= status < HTTPStatus.MULTIPLE_CHOICES:
        return False
    try:
        answer = json.loads(body)
    except ValueError:
        return False
    key = answer.get("key") if isinstance(answer, dict) else None
    message_id = key.get("id") if isinstance(key, dict) else None
    return isinstance(message_id, str) and bool(message_id)


class EvolutionProvider:
    """The ``NotificationProvider`` that speaks to a self hosted Evolution API instance."""

    def __init__(
        self,
        gateway: EvolutionConfig,
        destination: str,
        *,
        timeout: float = REQUEST_TIMEOUT_SECONDS,
    ) -> None:
        self._gateway = gateway
        self._destination = destination
        self._timeout = timeout

    def deliver(self, text: str) -> bool:
        """Deliver ``text``; ``True`` when the gateway accepted it, ``False`` on any failure."""
        call = send_text_request(self._gateway, self._destination, text)
        request = urllib.request.Request(
            call.url, data=call.body, headers=call.headers, method="POST"
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                status: int = response.status
                body: bytes = response.read()
        except urllib.error.HTTPError as refused:
            return self._failed(f"the gateway answered {refused.code}", http_status=refused.code)
        # URLError, a timeout and a reset connection are all OSError; ValueError is a body or a
        # URL the client could not handle. None of them may reach the engine as a raise (I2).
        except (OSError, ValueError) as unreachable:
            return self._failed(f"the gateway could not be reached: {type(unreachable).__name__}")

        if not was_accepted(status, body):
            return self._failed("the gateway answered without a message id", http_status=status)
        return True

    def _failed(self, reason: str, *, http_status: int | None = None) -> bool:
        # Only the reason and the status are logged: the request carries the API key in a header
        # and an exception text may carry the URL (I5).
        _logger.warning(
            "gateway send failed: %s",
            reason,
            extra={"event": "gateway_send", "reason": reason, "http_status": http_status},
        )
        return False
