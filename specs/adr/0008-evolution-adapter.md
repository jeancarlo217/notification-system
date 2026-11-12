# 0008. The Evolution adapter

Status: accepted, 2026-11-12. Derives from `specs/foundation.md` and loses to it. It records code
shape only, for the delivery of backlog B8.

## Context

Foundation section 4 sizes the notification provider at one operation, deliver this text to the
configured destination and say whether it was accepted, and names Evolution API as one adapter
behind it. The spike that closed OQ-1 on 2026-10-27 proved the vendor call by hand, and
`specs/dependencies.md` records its shape for the pinned 2.3.7. The owner decided on 2026-09-02
that the adapter speaks HTTP through the standard library. Backlog B8 lists what the adapter owes:
a timeout on every call, every vendor failure mapped to `False` and never raised (I2), acceptance
read from `key.id`, the API key in no log line (I5), and `get_provider` returning it.

## Decision

**One module, `core/evolution.py`, in two layers.** The request and the reading of the answer are
pure: `send_text_request` turns the gateway configuration, the destination and the text into a
URL, two headers and a body, and `was_accepted` turns a status and a body into a boolean. The
transport is `EvolutionProvider.deliver`, a single `urllib.request.urlopen` with a timeout.

**Acceptance is a successful status and a message identifier.** A 2xx whose body is not a JSON
object carrying a non empty string at `key.id` is a failure, because a proxy page or an empty
answer proves nothing was queued. As the spike recorded, this is acceptance by the gateway and
not delivery to a phone.

**Every failure is `False`.** An HTTP error status, a refused connection, a timeout and an
unreadable body all return `False`, which the engine writes as the day's list in the `failed`
state and retries within the hour. Nothing is retried inside the adapter: the retry is the
engine's, where it is persisted and visible.

**The timeout is fifteen seconds, a module constant.** It is how long a machine waits and not a
value the business tunes, on B17's precedent.

**A failure is logged with its reason and its status and nothing else.** The request carries the
API key in a header and an exception text may carry the URL, so neither is ever handed to the
logger.

**`get_provider` builds the adapter from the two accessors of ADR 0001**, the gateway and the
destination, and raises `ImproperlyConfigured` where no gateway is configured, which is phase
one. The engine turns that raise into a `failed` row and lets it stay loud.

## Consequences

The adapter is tested without the vendor and without mocking the HTTP client. The two pure
functions are tested as values. The transport is tested against a gateway this project's own test
file stands up on the loopback address, a real socket that answers what the test scripted, so the
refused connection and the timeout are observed. That is a deliberate reading of the rule in
`specs/testing.md` against the network in a unit test: nothing leaves the machine and nothing the
project does not own is faked.

One test speaks to a real instance and is skipped unless `EVOLUTION_LIVE_SEND=1` is set, because
it puts a message in the configured group. It is not skipped merely where no instance is
configured, as `specs/testing.md` words it, since a developer whose `.env` names a paired
instance would otherwise message the company group on every run of the suite.

The host side port Evolution is published on becomes `EVOLUTION_PORT`, read only by Compose like
`WEB_PORT` and for the same reason: the production host already runs other services.
