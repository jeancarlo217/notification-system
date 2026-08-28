# Testing and development method

Derives from `specs/foundation.md` and loses to it. This is the method every implementation
window follows; it is not a style guide, it is how correctness is produced here.

## Two windows

Window A writes the failing tests as behaviour and implements nothing. Window B implements the
minimum that turns them green and may not edit a test; a test that looks wrong is a finding
reported back, never a licence to rewrite it. Design happens under green, never while a test is
red. Never write the test after the code, never weaken a test to make it pass.

## Behaviour, never implementation

A test asserts the returned value, the emitted error, the persisted state or the observable
effect, and changes only when a requirement changes. One behaviour per test. Every test names the
identifier it implements (I1 through I7 from the foundation, or a task spec requirement), so a
requirement with no test is visible by grep and a test with no identifier is a candidate for
deletion.

## Decisions versus effects

A decision is pure: plain data in, plain data out, no clock, no network, no database. In this
project the decisions are the schedule computation (which warnings are owed, given records,
thresholds and today's date), threshold evaluation, message rendering, and CSV row shaping. They
carry the bulk of the tests and need no Django machinery to run.

An effect is I/O: the database, the clock, the outbound WhatsApp call, the emitted log. Effects
sit behind narrow interfaces with a real adapter and a test fake, and each interface is the size
of what the product needs, never the size of the vendor's API. The notification provider has one
operation. If a piece of logic can only be tested with the network or a live Evolution instance,
it was factored wrong.

Do not mock what you do not own: fake the provider interface, never the vendor SDK or its HTTP
client. Integration tests with the real Evolution adapter are few, exist only to prove the seam
speaks to the real thing, and are gated on the OQ-1 spike.

## The clock is an effect

Anything that depends on "now" receives the time as a value or through an injected clock, in the
America/Campo_Grande timezone. I3's acceptance test advances the injected clock across missed
days. A test that sleeps is a defect.

## Idempotency at every retry surface

The daily engine can run twice, by scheduler and by hand at once. Its canonical test is: run it
twice, observe one effect (I1). Any future retry surface (a webhook, a resend button) carries the
same test shape from birth.

## Gates and claims

CI blocks on ruff, `mypy --strict`, pytest and the secret scan, and the gates exist before the
code they govern. A state claim ("tests pass") is written only with the command that verified it.
Measurements are not tests: record them with device, versions, fixture and date in the log, never
as a flaky CI gate.
