---
name: docs-sync
description: Check whether the specs are still true, both against each other along the authority chain and against the code. Use when the user wants to verify the documentation matches reality, find a derived document that drifted from the foundation, or audit doc accuracy. Triggers on requests like "check docs", "are the specs up to date", "/docs-sync".
---

# Docs sync

The documentation here is the **authority chain**, and "out of sync" has a precise meaning: a derived
document asserting something the authority did not say, or a document asserting something that is not
true on disk.

The chain: `specs/foundation.md` then `CLAUDE.md` then `specs/adr/` then the skills under `.claude/`.
Where a derived document and the foundation disagree, the foundation wins and the derived one is wrong.

**Search for the contradiction, do not read for confirmation.** A document declaring itself complete is a
hypothesis, not a measurement.

## 1. The orphan check

A constraint that exists only in a derived document is a constraint nobody ratified. For each constraint
in `CLAUDE.md` and each rule a skill asserts, grep the foundation for the thing it asserts. Three
outcomes: it resolves upward and the digest is correct; it resolves upward but says something different,
which is drift and the authority wins; or nothing upward says it, which is an orphan. An orphan is
reported, never deleted and never promoted on your own: either the owner ratifies it into the foundation
or an ADR, or it was never a rule.

## 2. Check the chain, downward

For each derived document, check that it does not contradict the foundation, that two accepted ADRs do
not describe the same thing two ways, that it does not reference a section, identifier or document that
does not exist, and that a recently closed decision completed its fan-out (the foundation, `CLAUDE.md`,
the ADR, one line in `specs/log.md`).

## 3. Check the documents against disk

Verification is reading the file and running the command, never trusting a summary. Useful sweeps:

```bash
grep -rnP '[\x{2014}\x{2013}]' specs/ CLAUDE.md .claude/   # em and en dashes are banned in prose
ls -A                                                       # does the layout the docs claim exist?
```

Confirm the factual claims still hold: the repository layout `CLAUDE.md` describes, the commands it
lists (only ones that exist), the hook list it states, and any pinned version, which is confirmed against
the lockfile and never remembered.

## 4. Report only what is wrong

Flag what is false or contradictory, not what is missing and tracked. For each finding: the file, the
exact excerpt, which authority it contradicts, and the correction. Say which side to fix; almost always
the derived document, except when the authority genuinely never decided, in which case the fix is to
raise the decision to the authority.

A checklist ordered by severity: contradicts the foundation, contradicts another accepted document,
false against disk, stale pointer. **And say plainly whether the tree is clean**, because a report that
lists only findings reads as incomplete when there are none.
