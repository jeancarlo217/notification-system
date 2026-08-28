---
name: fix
description: Run the checks for the modified files, then fix what they report. Use when checks are failing, when the user says the lint or the types are broken, or asks to fix what CI reports. Triggers on "/fix".
---

Run the checks (`/quality-gate` has the list and the honesty rules about which exist yet), then fix every
error or warning reported. Scope commands to the modified paths where the tool allows it.

Do not suppress with `# noqa` or `# type: ignore` unless there is no alternative, and justify it in a
comment when you must. `mypy --strict` allows no `Any` without a justifying comment.

**Generated artifacts are never hand-edited.** A migration is generated with `makemigrations` and never
hand-authored; if a generated file is among the modified paths, regenerate it and fix its source instead.
Hand-editing one produces a green local run and a red CI, which is the worst of both.

If the fix a check demands would change behaviour a test pins, stop: that is a requirement conversation
(`specs/foundation.md`), not a lint fix.
