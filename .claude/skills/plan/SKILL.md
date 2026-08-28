---
name: plan
description: Plan a feature before writing any code, grounded in the canon and the codebase, then wait for confirmation. Use when the user asks to plan a feature before code, wants an implementation approach, or says plan this. Triggers on "/plan".
argument-hint: "[feature description | path/to/spec.md]"
---

Plan the work described by: $ARGUMENTS

Run this INLINE, in this conversation. If `$ARGUMENTS` points to a file, read it first; otherwise treat
it as the feature description. **Produce a plan only, write no code.**

## 1. Restate the requirement and trace it to its authority

Restate the goal and scope in clear English. Call out anything ambiguous and ask before assuming: a
sentence that admits two readings is a defect, not a style issue.

Trace the work through the chain: `specs/foundation.md` (the source of truth) then `specs/adr/` (code
shape) then `CLAUDE.md`. Where a derived document and the foundation disagree, the foundation wins. Cite
the specific thing: an invariant I1 to I7, a numbered foundation section, an ADR section. If the work
traces to nothing, that is the finding: surface it rather than planning around a guess, because a feature
nobody ratified is scope creep against foundation section 10.

## 2. Check the open questions before planning around them

Three are live (foundation section 11): **OQ-1** blocks the Evolution API Compose service and the
adapter's integration test, **OQ-2** blocks deployment configuration, **OQ-3** blocks only the final
message wording. If the work depends on one, say which and stop rather than inventing the answer.

## 3. Ground it in the shape the foundation decided

- **Decision or effect?** Pure decisions (schedule computation, threshold evaluation, message rendering,
  CSV shaping) take plain data in and out, no clock, no network, no ORM, and carry the bulk of the tests.
  Effects (database, clock, Evolution HTTP, logging) sit behind narrow interfaces with a real adapter and
  a test fake.
- **Does it send?** Then it needs the idempotency uniqueness (I1) and a visible failure state (I2).
- **Does it depend on "now"?** The time arrives as a value or an injected clock, in America/Campo_Grande,
  computed from persisted records (I3).
- **Is the value business data?** Thresholds, the destination number, the template, the secret path are
  configuration, never literals (I4).
- **Does it handle a request?** The audit entry (I6) and the secret-path redaction (I7) live on shared
  paths (middleware, the logging config), never in each view's diligence.

## 4. Break into ordered phases, test-first

Ordered phases in the two-window protocol: one pass writes the failing tests as behaviour (`test`),
another implements the minimum to green (`implement`). `specs/testing.md` is the method. Name the
invariant or foundation section each phase carries and stop there: the acceptance test in the foundation
is already the behaviour, and a plan that transcribes it has made a second copy that drifts.

Framework files are generated, never hand-written: `django-admin startproject`, `manage.py startapp`,
`makemigrations`. Lead each phase with those commands, and sequence so each phase leaves the suite green.

## 5. Flag risks and dependencies

Risks, unknowns, ordering constraints, and any new dependency, which is researched against its current
documentation and recorded in `specs/dependencies.md`, never asserted from memory. If you cannot verify,
say so and give a confidence level.

## 6. Present and wait

Present the plan and STOP. Wait for explicit confirmation before writing any code.
