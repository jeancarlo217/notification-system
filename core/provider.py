"""The notification provider seam (backlog B7, foundation section 4).

One operation, sized by what the product needs: deliver this text to the configured
destination and report whether it was accepted. Evolution API is the one adapter behind this
interface (backlog B8, ``core/evolution.py``).
"""

from typing import Protocol

from django.core.exceptions import ImproperlyConfigured

from deadliner.config import get_config, get_evolution_config


class NotificationProvider(Protocol):
    """The narrow interface the alert engine sends through."""

    def deliver(self, text: str) -> bool:
        """Deliver ``text`` to the configured destination; ``True`` when accepted.

        An adapter maps every vendor failure to ``False``, never an exception (I2).
        """
        ...


def get_provider() -> NotificationProvider:
    """The provider the daily command sends through, resolved at call time.

    Where no gateway is configured, which is phase one, resolving a provider is a loud
    configuration error and never a silent no-op.
    """
    # Imported here so the seam does not depend on its adapter at import time.
    from core.evolution import EvolutionProvider

    gateway = get_evolution_config()
    if gateway is None:
        raise ImproperlyConfigured(
            "No notification provider is configured: set EVOLUTION_BASE_URL, "
            "EVOLUTION_INSTANCE_NAME and EVOLUTION_API_KEY to send through Evolution API."
        )
    return EvolutionProvider(gateway, get_config().whatsapp_destination)
