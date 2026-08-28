"""The notification provider seam (backlog B7, foundation section 4).

One operation, sized by what the product needs: deliver this text to the configured company
number and report whether it was accepted. Evolution API becomes one adapter behind this
interface in B8, after the OQ-1 spike closes.
"""

from typing import Protocol

from django.core.exceptions import ImproperlyConfigured


class NotificationProvider(Protocol):
    """The narrow interface the alert engine sends through."""

    def deliver(self, text: str) -> bool:
        """Deliver ``text`` to the configured company number; ``True`` when accepted.

        An adapter maps every vendor failure to ``False``, never an exception (I2).
        """
        ...


def get_provider() -> NotificationProvider:
    """The provider the daily command sends through, resolved at call time.

    The Evolution adapter arrives with B8; until then resolving a provider is a loud
    configuration error, never a silent no-op.
    """
    raise ImproperlyConfigured(
        "No notification provider is configured: the Evolution adapter is delivered by B8, "
        "after the OQ-1 spike closes."
    )
