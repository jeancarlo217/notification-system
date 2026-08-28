---
allowed-tools: Bash(cat *), Bash(ls *)
name: test
description: Write the failing tests for a task, as behaviour, implementing nothing. Use whenever the user asks for tests, mentions TDD, red tests, test-first, an invariant (I1 to I7), or dispatches Window A of the two-window protocol. Triggers on "/test", "write the failing tests", "red tests", "Window A". Not for running an existing suite, which is the quality gate, and not for making tests pass, which is the `implement` skill.
---

# Write the failing tests

Write **tests that fail**, plus the minimum production signatures for them to compile and fail. Implement
nothing. The `implement` pass makes them green using these tests as a contract it may not edit, which only
works if the contract came from the requirement rather than from an implementation you had in mind.

## The method, injected because you cannot write a test here without it

This is `specs/testing.md`, loaded from disk right now. It is the authority; do not open it again.

!`cat specs/testing.md`

---

## 1. Read before writing, and read from disk

1. The requirement: the foundation section or invariant (`specs/foundation.md`, I1 to I7) the prompt or
   the task names. **Its acceptance test is your test.** Do not test anything gated behind an open
   question (OQ-1 to OQ-3); if the task depends on one, stop and report.
2. Any ADR the task names, for the code shape you must not invent around.
3. The code you build on, in full.

Then invoke the **`solid`** skill and follow it. Read what the task points at and nothing else "just in
case".

## 2. What a test asserts

**Behaviour, never implementation**: the returned value, the emitted error, the persisted state, the
observable effect. Never a private shape, never an internal call order. A test changes only when a
requirement changes.

**Name the behaviour as a domain sentence** (`a_failed_send_is_visible_and_retried_next_run`, never
`test_alert_2`), and **name the identifier** (`I2`) in the test name or a single comment, so a requirement
with no test is visible by grep. One behaviour per test; arrange, act, assert, visibly.

### The three ways a red test still pins the wrong thing

- **Implementation-coupled**: it mocks an internal collaborator, reaches a private, or asserts through a
  side channel. The tell: it breaks on a refactor while behaviour is unchanged.
- **Tautological**: the expected value is recomputed the way the code computes it, so it can never
  disagree with the implementation. Expected values are literals from an independent source: the
  invariant's acceptance test, a worked calendar example.
- **Unwitnessed happy path**: you tested that the rule fires and never that it stays quiet. Every
  conditional rule needs both sides. The canonical cases here: I1 needs "run twice, one send", and I3
  needs both "owed and sent" and "not yet owed and not sent".

## 3. Seams

Tests live at public boundaries. The decisions (schedule computation, threshold evaluation, message
rendering, CSV shaping) are pure and carry the bulk of the tests with no Django machinery. The effects
are faked at their interface: the notification provider (one operation), the clock (injected, never
`sleep`, never the real time). **If a piece of logic can only be tested with the network or a live
Evolution instance, it was factored wrong**; report that as a design finding instead of reaching for a
heavier harness. Integration tests with the real adapter are few and are gated on OQ-1.

## 4. Mechanics

- No logic in a test: no loops, no conditionals, no computed expectations.
- DAMP over DRY: keep the field the test is about visible in the body.
- Do not test trivial code, generated code, a third-party library, or a future that does not exist.
- **Signatures only**: the minimum production surface for the test to compile and fail. Not the body.

## 5. Touching a test that already exists

Only for a mechanical ripple (a signature gained a parameter). No existing assertion may be weakened,
reworded or deleted. If making an existing test compile seems to require changing what it asserts, stop
and report: that is a requirement change, and requirements change in `specs/foundation.md` first.

## 6. Deliver

Run the suite yourself and report real output, never an estimate: the tally with each red and its failure
message (new tests fail, existing tests stay green), before and after test counts per file, lint and type
check output, `git diff` summary when a repository exists, every choice the task did not pin, and anything
you believe is wrong in the task or the canon.

## 7. Stop and report

> If the task contradicts `specs/foundation.md` or an ADR, stop and report instead of choosing. The canon
> wins, and the correction is recorded before you continue.

**Language:** code, test names, comments and reports are in English.
