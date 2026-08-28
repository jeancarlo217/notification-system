"""Correlation context on the logging path (backlog B6, foundation section 8).

The keys a line needs to be correlated (the request or run it belongs to, and who submitted it)
are bound once, at the edge of a request or a run, and injected into every record written while
that context is alive.
"""

import contextvars
import logging
import uuid
from collections.abc import Callable, Mapping

from django.http import HttpRequest, HttpResponse

CLOUDFLARE_CLIENT_IP_HEADER = "CF-Connecting-IP"
CLOUDFLARE_COUNTRY_HEADER = "CF-IPCountry"

_request_logger = logging.getLogger("deadliner.request")

_LogContext = Mapping[str, str | None]

_bound: contextvars.ContextVar[_LogContext | None] = contextvars.ContextVar(
    "log_context", default=None
)


def bind_log_context(**keys: str | None) -> contextvars.Token[_LogContext | None]:
    """Add ``keys`` to the context every log record carries, until the token is reset."""
    return _bound.set({**current_log_context(), **keys})


def reset_log_context(token: contextvars.Token[_LogContext | None]) -> None:
    """Undo one ``bind_log_context``, so bound keys never outlive their request or run."""
    _bound.reset(token)


def current_log_context() -> _LogContext:
    """The keys bound right now, empty outside any request or run."""
    return _bound.get() or {}


class LogContextFilter(logging.Filter):
    """Copies the bound context onto every record, whichever logger wrote it."""

    def filter(self, record: logging.LogRecord) -> bool:
        for key, value in current_log_context().items():
            setattr(record, key, value)
        return True


class RequestContextMiddleware:
    """Binds one correlation key and the submitter's origin for the life of a request.

    The address and the country come from Cloudflare's forwarding headers and from nowhere else
    (foundation section 6): a direct request carries no origin, and inventing one from the socket
    would put a Cloudflare address, or a lie, into the audit trail (OQ-2).
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        token = bind_log_context(
            request_id=uuid.uuid4().hex,
            client_ip=request.headers.get(CLOUDFLARE_CLIENT_IP_HEADER),
            country=request.headers.get(CLOUDFLARE_COUNTRY_HEADER),
        )
        try:
            response = self.get_response(request)
            # Django logs a 4xx or 5xx from outside the middleware chain, where the bound context
            # is already gone, so the correlated line about a request is this one.
            _request_logger.info(
                "request",
                extra={
                    "event": "request",
                    "method": request.method,
                    "path": request.path,
                    "status": response.status_code,
                },
            )
            return response
        finally:
            reset_log_context(token)
