"""The audit trail of foundation section 6 (backlog B6).

With no login, this entry is the only answer to who entered a record (I6). The visitor's address
and country are bound per request by ``deadliner.log_context``; what a caller adds here is which
record was touched and which submitter it belongs to. The address is observed and the name is
asserted, and the entry carries both because they fail in different directions.
"""

import logging

_audit_logger = logging.getLogger("core.audit")


def log_service_submission(service_id: int, submitter_id: int) -> None:
    """Record one accepted form submission against the record it wrote and its submitter (I6).

    The submitter is the person who registered the record, which an edit does not reassign
    (ADR 0006).
    """
    _audit_logger.info(
        "service submission",
        extra={
            "event": "service_submission",
            "service_id": service_id,
            "submitter_id": submitter_id,
        },
    )
