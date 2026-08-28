"""Redaction of the secret path segment on the logging path (I7).

Request paths reach the logs by default, and the segment is the credential guarding the whole
application, so it is removed from every record before any handler writes it.
"""

import logging

from django.core.exceptions import ImproperlyConfigured

from deadliner.config import get_config

REDACTED_SEGMENT = "[secret-path]"


class SecretPathRedactionFilter(logging.Filter):
    """Replaces the configured secret path segment with a placeholder in every record it sees.

    Installed on the handlers rather than on one logger, so a record from any logger in the
    process passes through it (I7). It never drops a line: the rest of the path stays readable.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        segment = self._configured_segment()
        if not segment:
            return True

        message = record.getMessage()
        if segment not in message:
            return True

        record.msg = message.replace(segment, REDACTED_SEGMENT)
        # The message is already interpolated above, so the arguments must go or logging would
        # apply them a second time to a string that no longer carries their placeholders.
        record.args = ()
        return True

    def _configured_segment(self) -> str:
        try:
            return get_config().secret_path_segment
        except ImproperlyConfigured:
            return ""
