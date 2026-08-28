---
name: github-workflow
description: Take approved work all the way out, the gate, the commits, the push and the pull request, in one invocation instead of three. Use when the user says ship it, commit and open the pull request, or otherwise wants the whole chain rather than one step of it. Triggers on "/github-workflow", "ship it", "commit and open a PR". For one step on its own, use "/quality-gate", "/commit" or "/pr" directly.
disable-model-invocation: true
---

# Ship the work

**This is a pointer, not a procedure.** The three steps are already written and this file does not carry
a second copy of any of them:

1. **`.claude/skills/quality-gate/SKILL.md`**, the checks CI will run.
2. **`.claude/skills/commit/SKILL.md`**, the gate plus atomic Conventional Commits. It does not push.
3. **`.claude/skills/pr/SKILL.md`**, the push, the pull request, and the required checks.

Read each one when you reach it. What follows is only what none of the three says.

**When the whole chain is appropriate at all.** Only when the work is finished and reviewed: the gate is
green and `code-review` returned no blocking finding. Never on `main`. If any of those is false, run the
step that is missing instead of the chain.

**Which repository you are in, and whether there is one.** Run `git rev-parse --show-toplevel` and say so
before anything else. If it fails, there is no repository yet: the answer is `git init` plus a first
commit, not a push.

**Where to stop when a step fails:**

| Fails at | State you are left in | What to do |
| --- | --- | --- |
| gate | nothing happened | fix, do not commit on red |
| commit | some commits may exist | finish the commits, do not push a half-told story |
| push | commits are local | recoverable and normal; retry or fix the remote |
| push succeeds onto a branch whose pull request already merged | the commit is on a recreated branch, outside the merge | cherry-pick onto a branch off the current `main` and open a new pull request. The tell is `* [new branch]` in the push output where you expected an update |
| pull request | the branch is pushed and public | open the pull request by hand rather than leaving it |

**Whether the fan-out ran.** If this work closed a decision, the canon change is part of this commit, not
a follow-up. Run the `fan-out` skill, which owns the target list.
