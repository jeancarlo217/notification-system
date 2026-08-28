---
allowed-tools: Bash(wc *)
name: writing-for-agents
description: Write or revise any document an agent reads in this project, so it is cheap to load and reliable to reach, a skill, CLAUDE.md, a spec, an ADR, a window prompt. Covers the loading tiers, pointer wording, the no-op test, and pruning duplication and sprawl. Use when creating or editing anything under .claude/ or specs/, when a document feels long, or when an agent ignored a rule that is written down. Triggers on "/writing-for-agents", "write a skill", "edit CLAUDE.md", "this doc is too long".
---

# Writing for agents

The reader has already read everything. **Explanation is waste and precision is the whole job.**

This skill governs the **form** of a document: what it costs to load, whether the agent reaches it,
whether it says anything twice. Whether the document is **true** is `docs-sync`.

## What tier 0 costs right now

!`wc -l CLAUDE.md`

---

## 1. The loading tiers, and a fact lives at exactly one

| Tier | What | Paid |
| --- | --- | --- |
| 0, always | the root `CLAUDE.md` | every turn |
| 1, task | `.claude/skills/*/SKILL.md`, fired by the `description` or `/name` | per task |
| 2, cited | `specs/`, the ADR registry | per citation |

A higher tier points rather than restates: a skill carrying its own copy of the method is the copy that
goes stale, and the agent obeys it without being able to tell which authority is wrong. Two budgets, and
every choice spends one: **context load** (an always-loaded line is paid whether or not it fires) and
**cognitive load** (which documents exist and when to reach for each).

## 2. Ladder down, do not pile up

Material belongs on the lowest rung where it still fires: an in-file step (needed every run), an in-file
reference (needed most runs, sits below the steps), or behind a pointer (needed on one branch out of
several). A document that carries every branch inline pays for all of them on every run.

## 3. A pointer carries where AND when

Every pointer states where to read and the condition that sends you there. A skill's `description`
carries the words a user would actually say. A pointer is not a summary: the moment you write the gist
beside the citation you have made a second copy, and it is the copy that goes stale. An unreached pointer
is worse than an absent one, because the material is then both unread and believed covered; if an agent
keeps missing a rule that is written down, the pointer is the defect.

**Hard dependency versus optional lookup, and the syntax follows.** A document that cannot do its job
without the target **injects** it; one that sometimes needs it points. In a `SKILL.md`, injection is the
`` !`command` `` preamble form (the shell runs before the content reaches the model, so the material
cannot be skipped; declare the command in `allowed-tools`), and a lookup is backticks plus the firing
condition, or a markdown link for a file inside the skill's own directory. In `CLAUDE.md`, `@path` is a
real import expanded at launch and paid every session, so it is only for a true tier 0 dependency;
backticks name a path without importing it. Injection is not a second copy: it is read from disk at fire
time, so there is one copy and nothing to drift.

## 4. The no-op test

**Delete the line and ask whether the agent's behaviour changes.** If it does not, the line was paying
context and buying nothing. Applied honestly this deletes a lot: anything the model already knows,
anything stated elsewhere in the same document, anything that reads as encouragement. When a sentence
fails, delete the whole sentence rather than shortening it. The test is behavioural: settle a
disagreement by running the document and watching what the agent does.

## 5. Three failure modes, named so a review can call them

- **Duplication**: the same fact in two places. One of the copies is already wrong.
- **Sediment**: a line that was true two revisions ago and now only looks true, a stale version, a
  document that no longer exists, a command that was never created.
- **Sprawl**: the document grew past where anyone reads to the end, so the rules at the bottom are
  decorative.

## 6. Leading words

A compact concept the model already has does more work than a paragraph. This project's own: **the
canon**, **the fan-out**, **the two windows**, **the gate**, **an invariant**, **a scar**, **stop and
report**, **decision versus effect**, **the injected clock**. Use the existing word rather than inventing
a synonym.

## 7. The rules that are specific to this tree

- English, always, in everything under `specs/` and `.claude/` and in code; user-facing template strings
  are Portuguese.
- No em dash and no double hyphen in prose, anywhere, enforced by `.claude/hooks/check-prose.sh`. A CLI
  flag in backticks is a flag, not prose.
- Cite by identifier: `I3`, `OQ-1`, `ADR-0002 section 4`, `foundation section 5`. A citation that
  resolves is worth more than a paraphrase that reads well.
- A lower layer never decides. A constraint that exists only in a derived document is a constraint nobody
  ratified; finding one is a defect to report.
- A closed decision fans out in one pass (`fan-out` owns the targets).
- State claims carry the command that verified them.

## 8. Writing a skill specifically

The `description` is the trigger and the only part loaded until the skill fires, so it carries the words
a user would actually say. One skill, one job. Do not restate a spec (injecting is different: it loads
the authority from disk at fire time). Practice what it preaches: a skill about lean documents that runs
to four hundred lines has refuted itself.

## 9. Done when

Every line survives the no-op test, nothing is stated twice at any tier, every pointer says where and
when, every citation resolves, and the document got **shorter** as it got better.
