# Decision log

One line per entry: `## [YYYY-MM-DD] <type> | <one line>`, with the types `version`, `decision`,
`finding` and `trap`. A wrong entry is corrected in place with a dated note, never deleted and
never appended over.

## [2026-08-28] version | foundation v0.1: canon written; core thesis, flat model, provider interface, 30/7/0 config thresholds, daily command, secret link with Cloudflare and audit, CSV export closed; OQ-1..3 opened.

## [2026-08-28] decision | .claude toolkit re-derived from the Ecobalance import: deleted backlog, linear-workflow, ticket, orchestrate, session-handoff, pr-review, worktree-commit-merge, rules/angular.md and the production-dump hook; rewrote the surviving skills against foundation v0.1; hooks now enforce prose, no-main-push and no-secrets-staged, stated in CLAUDE.md.

## [2026-08-28] decision | specs/backlog.md created by owner request: B1..B11 sequence version 1 (B8 blocked on OQ-1, B11 on OQ-2), F1..F3 hold the post-v1 goals; it carries execution state only and derives from foundation v0.1.

## [2026-08-28] finding | The scaffold found on disk at B1 start had been generated with Django 6.0.7 and pip, not the 5.2 LTS of foundation section 8; framework files were regenerated with the 5.2.17 CLI (project `deadliner`, app `core`), the hand-written hello-world view was dropped as untraced code.

## [2026-08-28] decision | Owner revision during B1: packaging is a plain venv with pip and pinned requirements files, replacing uv; foundation section 8 and 13, CLAUDE.md, backlog B1, the quality-gate and systematic-debugging skills updated in the same pass; specs/dependencies.md created with the pins and sources.

## [2026-08-28] decision | B1 shape, recorded in specs/dependencies.md and not in an ADR: gunicorn serves WSGI in the container, Compose runs migrate then gunicorn with SQLite on the `data` volume, CI is GitHub Actions (ruff, ruff format, mypy, pytest, gitleaks-action), local secret scan is gitleaks in Docker via `just secret-scan`; settings read DJANGO_SECRET_KEY, DJANGO_DEBUG, DJANGO_ALLOWED_HOSTS and DJANGO_DATABASE_PATH from the environment so no key sits in the repository (I5), the one-boundary design stays with B2.

## [2026-08-28] trap | The hooks in .claude/hooks depend on `jq`, which was absent on the owner's Windows machine, so they had been failing silently; installed via winget together with `just`. On Git Bash, a Docker `-v host:/repo` mount needs `MSYS_NO_PATHCONV=1` or `/repo` is rewritten to a Windows path; the justfile carries it.
