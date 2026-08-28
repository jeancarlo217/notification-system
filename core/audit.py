"""The audit trail of foundation section 6 (backlog B6).

With no login, this entry is the only answer to who entered a record (I6). The submitter's
address and country are bound per request by ``deadliner.log_context``; what a caller adds here
is which record was touched.
"""

import logging

_audit_logger = logging.getLogger("core.audit")


def log_service_submission(service_id: int) -> None:
    """Record one accepted form submission against the service it wrote (I6)."""
    _audit_logger.info(
        "service submission",
        extra={"event": "service_submission", "service_id": service_id},
    )
