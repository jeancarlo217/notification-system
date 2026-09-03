---
allowed-tools: Bash(cat *), Bash(git *)
name: implement
description: Write the minimum production code that turns failing tests green, then refactor under green without touching the tests. Use whenever the user asks to implement a feature, make failing tests pass, or dispatches Window B of the two-window protocol. Triggers on "/implement", "make the tests pass", "make it green", "Window B". Not for writing the tests themselves, which is the `test` skill.
---

# Minimum to green

The red tests in the tree are the **executable specification**, written by another pass so the
implementation cannot shape itself to a contract it authored. Write the minimum production code that turns
them green, then refactor under green.

**If there are no red tests, stop and report that the contract is missing**; let the `test` pass run
first. Code written before its test tests nothing and agrees with its own bugs.

## The method, injected because you cannot finish without it

This is `specs/testing.md`, loaded from disk right now. It is the authority; do not open it again.

!`cat specs/testing.md`

## The working tree right now

!`git status --short 2>&1 | head -20`

---

## 1. The rule that defines this window

**Do not modify the test module. Byte-identical when you are done.** A test that looks wrong is a finding
you report, never a licence to rewrite the contract you exist to satisfy. Do not add a dependency, a
model field or an abstraction the tests do not force.

## 2. Read before writing

The red tests, every one of them, the way you would read a spec. Then the foundation sections and ADRs
the task names. Then invoke the **`solid`** skill, spending it in the refactor step and not before.

## 3. Minimum first

No production code except to make a failing test pass, and no more than is sufficient. Faking a return
until a second test forces the real implementation is triangulation, not cheating. Do not anticipate: a
branch no test exercises is untested by construction. Make one test pass, run the suite, take the next;
a pass that writes everything and runs the gate once at the end cannot tell which change broke what.

## 4. Refactor under green, never under red

Make it work, make it right, make it fast, in that order. Under green, `solid` applies: single
responsibility, names that reveal intent, guard clauses over nesting, two similar blocks stay two blocks
until a third repetition. Write code an agent can navigate: distinctive greppable names over `Service` or
`handler`, explicit types at every boundary, error messages that carry the value and the expectation.

Keep the project's own shapes: decisions stay pure (no clock, no network, no ORM inside them), effects
stay behind their narrow interfaces, "now" arrives as a value, and business values (thresholds, the
alert destination, the templates, the secret path) come from configuration, never literals (I4).

## 5. Comments

The default is zero. An inline comment earns its place only when the correct code looks wrong, so that
without it someone "fixes" it. A decision the canon documents is cited by identifier (`I3`, `OQ-1`),
once, on the line whose shape it made surprising, and never restated. A docstring on a public surface
saying what it guarantees is welcome, one to three lines.

## 6. Scope

Touch only what the task scoped and the tests force. No drive-by renames, no opportunistic cleanups. If
something outside the scope is broken, report it, do not fix it.

## 7. Deliver

Run the full gate yourself (`/quality-gate`) and report real output: the suite with exact counts, lint
and types, the diff with confirmation that the test module is byte-identical, every choice the task left
to you, anything you implemented that no test witnesses, and anything stale or wrong you found. Evidence,
not assertion: a report claiming green without the output gets re-run.

## 8. Stop and report

> If the task contradicts `specs/foundation.md` or an ADR, stop and report instead of improvising.

**Language:** code, comments and reports are in English. User-facing strings in templates are Portuguese.
