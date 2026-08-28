---
name: pr-summary
description: Write a pull request body for the current branch. Use when the user wants a PR description, a summary of the branch changes, or a body prepared before opening the PR. Triggers on requests like "summarize my changes", "write a PR description", "/pr-summary".
---

# PR summary

Write the body for the current branch's pull request. **Produce the text; do not open the pull request.**
That is `/pr`.

## 1. Read what actually changed

```bash
git rev-parse --abbrev-ref HEAD
git log origin/main..HEAD --oneline
git diff origin/main...HEAD --stat
git diff origin/main...HEAD
```

Read the diff, not just the commit subjects. A body derived from commit subjects repeats what the
reviewer can already see and adds nothing.

## 2. The body

English, no em dashes, no double hyphens, no AI or Co-Authored-By attribution trailer anywhere.

Four parts, dropping any that would be empty rather than padding it:

**What this changes, and why.** One short paragraph in plain language. Lead with the behaviour that is
different now, not with the files.

**The trace.** Which invariant (I1 to I7), foundation section or ADR section this implements, cited by
identifier. This is the part a reviewer actually needs, because work that traces to nothing should not
exist.

**What a reviewer should look at hardest.** Name the risky part rather than making them find it: a
decision that moved, a migration, a place where the change was arguable. A pull request that claims
everything is straightforward gets a shallow review.

**What is deliberately not here.** Scope left out on purpose, a follow-up, an open question you hit
(OQ-1 to OQ-3). This is what stops a reviewer asking for something that was decided against.

## 3. One thing worth checking before you hand it over

If the change touches a decision, the fan-out is part of the work and belongs in the body: say which
documents moved (`specs/foundation.md`, `CLAUDE.md`, the ADR, `specs/log.md`), so the reviewer can check
it. A pull request that changes a decision in one place only is incomplete.
