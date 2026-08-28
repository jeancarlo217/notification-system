---
name: pr
description: Push the current branch and open a pull request against the base, then point at the required CI checks. Use when the user asks to open a pull request, push the branch, or ship the work for review. Triggers on "/pr".
argument-hint: "[base-branch, default main]"
disable-model-invocation: true
---

Open a pull request for the current branch. Base branch: $ARGUMENTS (default `main` when empty).

## 1. Validate preconditions (stop on any failure)

Run `git fetch origin` first so the comparisons are accurate, then check all of:

- **A repository and a remote exist.** If `git rev-parse` fails there is no repository yet, and the answer
  is `git init` plus a first commit, not a push. If `git remote -v` is empty, stop and say so.
- Current branch is not the base. If on `main`, stop: branch first. Main never receives a direct push.
- There are commits ahead of the base: `git log origin/<base>..HEAD --oneline` lists at least one.
- No pull request exists for this branch (`gh pr list --head <branch>`). If one exists and is **merged**,
  the branch you are standing on is finished: pushing to it recreates a dead branch and orphans the
  commit outside the merge. The work belongs in a new branch off the current `main`.
- **The gate is green.** Run `/quality-gate` if it has not run since the last commit.

## 2. Push the branch

```bash
git push -u origin <branch>
```

Read the output before believing it: `* [new branch]` on a branch you believed was already published
means the remote copy was gone, which is the merged-pull-request case above.

Republishing your own branch after a rebase uses `--force-with-lease`, never a bare `--force`. When the
lease refuses with `stale info`, somebody pushed: **go look at what they pushed.** Do not fetch and
retry, because a fetch immediately before the leased push disarms the lease.

## 3. Open the pull request

```bash
gh pr create --base <base> --fill
```

`--fill` derives the title and body from the commits; `/pr-summary` writes a better body when the change
deserves one. **No AI or assistant attribution trailer** anywhere in the body.

## 4. Point at the required checks

```bash
gh pr checks --watch
```

Merge only when the required checks are green. A red build is not merged and is not overridden.
