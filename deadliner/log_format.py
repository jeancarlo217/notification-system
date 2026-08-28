"""The structured log line (backlog B6, foundation section 8).

One JSON object per record, so the audit trail is queryable rather than prose.
"""

import datetime
import json
import logging
from typing import Any
from zoneinfo import ZoneInfo

from django.core.exceptions import ImproperlyConfigured

from deadliner.config import get_config

_UTC = ZoneInfo("UTC")

# Everything logging itself puts on a record. What remains is what a caller passed as `extra`,
# plus the keys the context filter bound, and that is what makes the line structured.
_STANDARD_RECORD_KEYS = frozenset(
    vars(logging.LogRecord(name="", level=0, pathname="", lineno=0, msg="", args=(), exc_info=None))
) | {"message", "asctime", "taskName"}


class JsonFormatter(logging.Formatter):
    """Renders a record as a single JSON object carrying its message and every bound key."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.datetime.fromtimestamp(
                record.created, tz=_timezone()
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update(
            {key: value for key, value in vars(record).items() if key not in _STANDARD_RECORD_KEYS}
        )
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def _timezone() -> ZoneInfo:
    try:
        return get_config().timezone
    except ImproperlyConfigured:
        return _UTC
