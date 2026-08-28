# Claude Code toolkit

Toolkit for the deadline notification system. It was imported from the Ecobalance ecosystem and
**re-derived against this project's canon on 2026-08-28**: seven Ecobalance-bound skills (Linear,
orchestrator, monorepo, worktrees), the Angular rule and the production-dump hook were deleted, and
every surviving skill was rewritten against `specs/foundation.md`. What was removed and why is one line
in `specs/log.md`.

Start from `CLAUDE.md` and `specs/foundation.md`. Everything under `.claude/` derives from them; a file
here that contradicts the canon is worse than an absent one, because the agent follows it and cannot
tell which authority is stale. A closed decision fans out into this folder when it changes something
enforceable (`fan-out` owns the pass).

## The mechanism model

- **A skill is content; a subagent is a context.** Reach for a subagent only when isolation is the point
  (the three `code-review` axes). Everything else stays a skill.
- **A prompt instruction is a request; a hook is enforcement.** Anything mechanically decidable that must
  hold every time belongs in `hooks/` or CI.
- **A side-effecting skill declares `disable-model-invocation: true`**, so it costs nothing until the
  owner types it: `commit`, `pr` and `github-workflow` set it.
- **A fact lives at exactly one tier and a higher tier points rather than restates.** The no-op test is
  the pruning gate: delete the line, and if the agent's behaviour does not change, it was paying context
  and buying nothing.

## `hooks/`, the only layer that is a guarantee

- **`check-prose.sh`** (PostToolUse on Write and Edit) blocks an em dash, en dash or double hyphen in
  markdown prose. Fenced blocks and inline code are stripped first.
- **`block-main-push.sh`** (PreToolUse on Bash) refuses a push that names `main` and any push while
  `main` is checked out, fail closed, until branch protection exists on the remote.
- **`block-secrets.sh`** (PreToolUse on Bash) refuses staging an env file or a SQLite database, and
  refuses `git add -A` or `git add .` while either sits untracked on disk (I5).

`settings.json` carries shared permissions and the hook registrations. `settings.local.json` is per
machine and gitignored.

## Skills

The two-window loop and its guards:

| Skill | What it does |
| --- | --- |
| [test](./test/SKILL.md) | Write the failing tests as behaviour, implement nothing. Window A |
| [implement](./implement/SKILL.md) | Minimum production code to green, tests byte-identical, design in the refactor step. Window B |
| [code-review](./code-review/SKILL.md) | Your own diff: machine gates first, then three isolated axes (Canon blocking, Spec blocking, Craft advisory), never merged into one list |
| [quality-gate](./quality-gate/SKILL.md) | The local mirror of CI, honest about which checks exist yet |
| [fan-out](./fan-out/SKILL.md) | Propagate a closed decision to every document in one pass. A decision is not closed until this has run |

The rest:

| Skill | What it does |
| --- | --- |
| [plan](./plan/SKILL.md) | Plan a feature against the canon, check the OQ gates, wait for confirmation |
| [onboard](./onboard/SKILL.md) | Read the canon before the code, trace the task to its authority |
| [fix](./fix/SKILL.md) | Run the checks, fix what they report, no suppressions |
| [commit](./commit/SKILL.md) | Gate then atomic Conventional Commits. Does not push |
| [pr](./pr/SKILL.md) | Push the branch, open the pull request, watch the checks |
| [github-workflow](./github-workflow/SKILL.md) | The whole chain (gate, commit, pr) as one pointer |
| [pr-summary](./pr-summary/SKILL.md) | Write the pull request body, including the trace |
| [docs-sync](./docs-sync/SKILL.md) | Check the specs against each other and against disk |
| [systematic-debugging](./systematic-debugging/SKILL.md) | Four phases, root cause first, aimed at this system's failure modes |
| [solid](./solid/SKILL.md) | SOLID, clean code, smells, complexity. Stack-agnostic, spent in the refactor step under green |
| [writing-for-agents](./writing-for-agents/SKILL.md) | Write anything an agent reads so it is cheap to load and reliably reached |

## Adding a file here

Create `.claude/skills/<name>/SKILL.md` with `name` and `description` frontmatter; the `description` is
what Claude matches on, so it carries the words a user would actually say. Check it against the canon
before adding it, cite what it derives from, and add it to this README. Everything written is in
English, with no em dashes and no double hyphens in prose (the hook enforces it here too).
