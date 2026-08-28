---
name: quality-gate
description: Validate the work locally before commit or PR, running the same checks CI will run. Stops you committing on red. Use before any commit or pull request, and whenever the user asks whether the work is ready or if the checks pass. Triggers on "/quality-gate".
argument-hint: "[optional scope note]"
---

# Quality gate

Local mirror of the checks CI runs. Green here means "safe to push", never "merge approved": only the
remote checks are authoritative for merging. Optional focus: $ARGUMENTS

## One stack, one gate

This project is a single Django application in a plain virtualenv with pinned requirements files,
checked by ruff, `mypy --strict` with django-stubs, pytest with pytest-django, and gitleaks. The
`justfile` at the root is the single definition CI shares; `just gate` is the whole gate in one word,
and CLAUDE.md lists every recipe.

```bash
just lint          # ruff check . and ruff format --check .
just typecheck     # mypy, strict, django-stubs plugin
just test          # pytest
just secret-scan   # gitleaks over the working tree, needs Docker running
just gate          # all four, in CI order
```

The migration check joins the gate from the first model onward (`just manage makemigrations --check`):
a model change with no migration is the cheapest real bug this gate catches. Until a model exists,
say it was skipped and why; **never report a pass for a check that has no surface to run on.**

## The sweep that belongs to no check

Look at what is about to be committed. Stop outright on: a secret or credential, an `.env` file carrying
real values, a SQLite database file, or anything that looks like production data (I5). The
`block-secrets.sh` hook guards staging, but the gate looks anyway, because the hook covers sessions and
not bare terminals.

## Report and block on red

Report each check you ran on its own line as PASS or FAIL, with the actual output for anything that
failed. **Say explicitly which checks you skipped and why** ("Docker not running", "no model exists"),
because a report that silently omits a check reads as a pass.

If anything is FAIL, state that the change is not ready to commit or push, and stop. Do not paper over a
red by skipping or deleting a test: weakening a test to make it pass is forbidden outright
(`specs/testing.md`), and if a test blocks you and you believe it is wrong, that is a conversation about
the requirement, in `specs/foundation.md`.

## Diff summary

Only when the gate passes, summarize the pending change (`git status --short`, `git diff --stat`) so the
scope can be sanity-checked. Flag anything unexpected: files outside the intended scope, a generated
artifact, a lockfile from a tool the project does not use, a dependency added to a requirements file
without a line in `specs/dependencies.md`.
