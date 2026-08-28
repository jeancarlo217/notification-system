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

## [2026-08-28] decision | Two-developer parallel plan recorded in specs/backlog.md: wave 0 the B8 spike plus OQ-2/OQ-3 answers, wave 1 B2 beside B3, wave 2 a screens-and-safety track (B4, B5, B6, B10) beside an engine track (B7, B9, B8 adapter), wave 3 B11 together; B5 and B6 share one developer because both edit the logging path.

## [2026-08-28] decision | B8 spike shape, on branch b8-evolution-spike: Evolution API pinned to evoapicloud/evolution-api:v2.3.7 (latest stable; the `latest` tag is a 2.4.0 rc) with its own postgres:15 and redis:7-alpine as neighbouring Compose services and volumes, opaque to web; only EVOLUTION_API_KEY and EVOLUTION_DB_PASSWORD come from .env; the spike steps are `just evolution-*` recipes; findings in specs/dependencies.md. OQ-1 stays open until one real message is delivered.

## [2026-08-28] finding | The Evolution documentation moved to docs.evolutionfoundation.com.br and its send-text page still documents the v1 body (`textMessage.text`); the 2.3.7 source takes top-level `text`. Git tags have no `v` prefix, Docker tags do.

## [2026-08-28] trap | The owner's machine had 0.2 GB free on C: on 2026-08-28; Docker Desktop answered `metadata.db: input/output error` and then hung, so the Evolution stack could not boot. Free disk space before `just evolution-up`; Docker Desktop's data disk grows as images are pulled.

## [2026-08-28] decision | B2 delivered by developer A: one configuration boundary, `load_config` in `deadliner/config.py` called once by the settings module, business values reached through `get_config()`; five `DEADLINER_*` variables with no default in code at all (I4 forbids the literal, overridable or not), one `ConfigError` listing every problem, and the secret path segment never repeated in an error text (I7). Shape in `specs/adr/0001-configuration-boundary.md`, the first ADR.

## [2026-08-28] decision | Two B1 settings behaviours tightened by B2: `DJANGO_DEBUG` now accepts only `0` or `1` and errors on anything else instead of reading it as off, and an empty `DJANGO_ALLOWED_HOSTS` with debug off is a boot error because that pair refuses every request.

## [2026-08-28] finding | Confirmed against the pins for B2, recorded in specs/dependencies.md: `python:3.13-slim` already carries the IANA time zone database so no `tzdata` pin is needed; `ZoneInfo` raises `KeyError` for an unknown name but `ValueError` for one that escapes the zone directory, so validation must catch both; `string.Formatter().parse` reports malformed braces as `ValueError` and yields positional and attribute access as ordinary field names.

## [2026-08-28] trap | The dotenv parser behind `just` refuses an unquoted value containing spaces, which the Portuguese message template has, so it is quoted in `.env.example`; `just` and Docker Compose both strip the surrounding quotes, verified by printing the loaded value through each rather than assuming they agree.

## [2026-08-28] trap | The gitleaks rule `generic-api-key` fires on any alphanumeric string of sixteen or more characters near the word secret, so tests of the secret path segment trip the C5 gate by nature. The fixture gives way, never the gate: obviously fake low entropy values instead of an allowlist over `tests/`, which would blind the scan exactly where a real credential could be pasted. B5 will meet the same rule.

## [2026-08-28] trap | `just setup` builds the virtualenv from whatever `python` is on PATH, which on Fedora 44 is 3.14 while the canon, the Dockerfile and CI are 3.13; the local venv was created with `python3.13` by hand and the recipe is still unfixed.

## [2026-08-28] trap | An image pulled while the disk was full stays corrupted after space is freed: evoapicloud/evolution-api:v2.3.7 had zero-byte dist/main.js and startup scripts, the container exited 0 silently and restart-looped. Remedy is `docker image rm` plus a fresh pull; Docker Desktop also needed a clean restart (kill lingering Docker Desktop.exe, `wsl --shutdown`). Recorded in specs/dependencies.md.

## [2026-08-28] finding | B8 spike verified up to the QR: Evolution 2.3.7 boots with its Postgres and Redis, migrations apply, instance `valeverde` created, QR generated. Pairing and the real send remain with the owner; OQ-1 still open.

## [2026-08-28] decision | Review window over B1, B2, B3 and the B8 spike on branch b8-evolution-spike after merging main: full gate green on the merged tree (ruff, `mypy --strict`, 86 tests, gitleaks, `makemigrations --check`); CLAUDE.md status and layout brought up to B3, backlog B3 marked merged and wave 0 reworded to the one-stack compose of foundation section 8, `just setup` pinned to Python 3.13 (closes the trap above). Orphans reported to the owner, not promoted: UI in Portuguese and English elsewhere, CLI-generated framework files, the comment rule and the prose rule exist in CLAUDE.md and the toolkit but not in the foundation.

## [2026-08-28] decision | Owner promoted the four orphans of the review window into foundation section 12 (UI in Portuguese and English elsewhere, CLI-generated framework files, the comment rule, the prose rule); CLAUDE.md standing rules unchanged and now derived. B8 pairing and real send deferred to 2026-08-29 with the company phone.

## [2026-08-28] decision | B4 shape, recorded here and not in an ADR: four function views in core/views.py (list, create, due date edit, complete as POST only) over two ModelForms in core/forms.py (registration with the three fields, due date alone), templates under core/templates/core with no external asset, routes named service-list, service-create, service-due-date, service-complete at the site root until B5 mounts them under the secret segment; LANGUAGE_CODE is pt-br so Django's own messages are Portuguese; Service.Status carries the Portuguese labels Ativo and Concluido, which the CLI turned into migration 0002.
