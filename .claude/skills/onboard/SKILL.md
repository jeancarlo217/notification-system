---
name: onboard
description: Onboard to a new task by reading the canon, exploring the codebase, and building the context needed to implement. Use when starting a new task, feature, or bug fix that requires understanding the project first. Triggers on requests like "onboard me", "get ready for this task", "/onboard".
---

# Onboard

The user has given the task as an argument. Use it to aim the reading.

## 1. Read the canon first, not the code

Much of this tree is intent rather than code, so the decisions live in the specs. Read in this order,
from disk rather than from a summary:

1. `CLAUDE.md`, the digest: the authority chain, the constraints C1 to C7, the key behaviors.
2. `specs/foundation.md` for the sections the task touches, and for the **scar** behind an invariant when
   you are about to build against one. Do not read all of it for a narrow task; read section 0.5, the
   plain-language soul, and then the cited sections.
3. `specs/adr/` for any code-shape decision that governs where things go (`specs/adr/README.md` lists
   what exists; it may be empty).
4. `specs/testing.md` before writing any test or any code.
5. The tail of `specs/log.md`, for what moved recently.

## 2. Trace the task to its authority

Name the invariant I1 to I7 or the foundation section the task derives from. If it traces to nothing,
that is the finding: surface it rather than inventing a spec. The same holds if it depends on an open
question (OQ-1 to OQ-3) that is still open.

## 3. Explore the codebase

Once code exists: which app, which module, which patterns the existing code follows. Verify with `ls`
rather than assuming a layout; early in this project many surfaces will not exist yet, and asserting one
from memory is how a plan builds on air.

## 4. Ask before assuming

Ask about anything genuinely ambiguous. A question costs a minute; a wrong assumption costs the
implementation. Never assert a library's behaviour from memory: confirm against the pinned version and
`specs/dependencies.md` once it exists, or say you could not and give a confidence level.

## 5. Where the output goes

Do not create a private notes file. Report the onboarding summary in the conversation; if something
deserves to persist, it is a change to the canon (through `fan-out`) or a line in `specs/log.md`.
