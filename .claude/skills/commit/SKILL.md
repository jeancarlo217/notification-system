---
name: commit
description: Run the pre-commit gate and create atomic Conventional Commits (does not push). Use when the user asks to commit, save the work, or create commits. Triggers on "/commit".
argument-hint: "[optional scope or message hint]"
disable-model-invocation: true
---

Create one or more commits for the staged work. Optional hint for scope or wording: $ARGUMENTS

## 1. Pre-commit gate, never commit on red

Run `/quality-gate`, which is the single definition of the checks. Do not restate a partial list here. If
any check fails, STOP: report what failed and do not commit.

## 2. Inspect what is staged

```bash
git status
git diff --staged
```

Read the staged changes to understand their purpose. If nothing is staged, stop and say so; this command
does not stage files for you.

**Two things that stop a commit outright** (I5): a credential or secret of any kind (the `.env` with real
values, an API key, the secret access path), and a database file or production data. A repository that
starts with a committed secret carries it in its history forever.

## 3. Compose an atomic Conventional Commit message, in English

One purpose per commit. Format `type(scope): short description`, type from `feat`, `fix`, `refactor`,
`test`, `docs`, `style`, `chore`, `perf`, `ci`. Subject imperative, lower case, no trailing period, no em
dashes, no double hyphens. If the subject needs an "and", that is two commits: split by purpose and stage
each separately (`git restore --staged <paths>` then `git add <paths>`).

**Do not add any AI or Co-Authored-By attribution trailer.** The committer of record is the developer.

## 4. Create the commits

```bash
git commit -m "type(scope): short description"
```

**Do not push.** Opening a pull request is `/pr`, and `main` never receives a direct push.

## 5. When the commit changes a decision, the fan-out is part of the change

A commit that closes or revises a decision is not finished when the code compiles. Run the `fan-out`
skill, which owns the target list. A decision that lands in code and not in the canon is a contradiction
waiting to be found.
