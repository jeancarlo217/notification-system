---
allowed-tools: Bash(tail *)
name: fan-out
description: Propagate a closed decision to every document it touches, in one pass, so the canon cannot contradict itself. Use whenever a decision is taken, changed, reopened or refused, whenever a requirement or an invariant moves, and whenever a session is about to end with something decided in chat that is not yet written down. Use it even when the change feels small. Triggers on "/fan-out", "propagate this decision", "update the docs for this", "we decided X", "record this in the canon".
---

# Fan out a decision

**A closed decision is not closed until it has been propagated.** Recording it in one document and
planning to update the rest later is how a canon acquires a contradiction.

Run this in the main session, not in a subagent: the output is edits the owner reviews as a diff.

## The tail of the log, so your entry matches the format

!`tail -5 specs/log.md`

---

## 1. Establish what actually changed

State it in one sentence before touching a file. A decision, an amendment and a correction are different
things and propagate differently:

| Kind | What it is | What it triggers |
| --- | --- | --- |
| **Decision** | something open is now closed, or something closed was reopened and re-decided | the full fan-out below, and a version bump on the foundation |
| **Amendment** | a higher document changed and a lower one must follow | the targets the change reaches, plus a dated note in each ADR touched |
| **Correction** | a document says something untrue and no decision moved | fix it, log one line, do not bump a version |

A **refusal** still propagates: a refusal written nowhere is proposed again in six months by somebody
acting in good faith. Refusals land in the foundation's non-goals or the decision log.

## 2. Find every target, by grep rather than by memory

```bash
grep -rn "I3\|OQ-1" specs/ CLAUDE.md .claude/
grep -rln "the distinctive phrase the old decision used" specs/ CLAUDE.md .claude/
```

The second grep is the one people skip and the one that finds the stale copy, because a document that
paraphrased the decision does not cite its identifier.

## 3. The targets, and what each one gets

Work down the authority chain. A lower document never decides: if the decision is not in the foundation
or an ADR first, stop and put it there before touching anything below.

| Target | What it gets | Skip when |
| --- | --- | --- |
| `specs/foundation.md` | the decision as law with what it buys and costs, its scar if it is an invariant, an entry in section 13, a version bump | the decision is code shape only, which is an ADR |
| `specs/adr/` | a dated note inside the owning ADR, or a new numbered file. An accepted ADR is superseded, never quietly rewritten | no code shape moved |
| `CLAUDE.md` | the compressed constraint or behavior, only if it is true for every task | the change is invisible to an implementing session |
| `specs/testing.md` | the method change | the method did not move |
| `.claude/skills/` | the procedure, if the decision changes how work is done | it changes what is true rather than how work runs |
| `specs/log.md` | **one grep-able line**, in the format the file's header states | never |

## 4. Verify, then report

```bash
grep -rn "<the old wording>" specs/ CLAUDE.md .claude/          # must return nothing
grep -rnP '[\x{2014}\x{2013}]' specs/ CLAUDE.md .claude/         # must return nothing
```

Report: which kind of change it was, every file touched and what each got, every target you skipped with
the reason, and anything you found stale while grepping that this decision did not cause.

**If a target contradicts the decision rather than merely lagging it, stop and report.** Two documents
disagreeing is not a propagation problem; it is a decision somebody needs to take.
