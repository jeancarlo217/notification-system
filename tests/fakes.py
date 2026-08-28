"""Fakes for the narrow effect interfaces (specs/testing.md, decisions versus effects)."""


class FakeProvider:
    """A notification provider that records texts and never touches a network.

    It fakes the ``NotificationProvider`` interface of ``core.provider``, never the vendor.
    """

    def __init__(self, *, accept: bool = True) -> None:
        self.accept = accept
        self.deliveries: list[str] = []

    def deliver(self, text: str) -> bool:
        self.deliveries.append(text)
        return self.accept
