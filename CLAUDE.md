# CLAUDE.md

This file is a digest. The single source of truth is `specs/foundation.md`; when the two disagree,
the foundation wins and this file is the one that is wrong. Fix this file, never code against it.

## Project status

B1 (scaffold), B2 (configuration surface), B3 (data model), B4 (registration and lifecycle), B5
(secret path and health endpoint), B6 (audit and structured logging), B7 (alert engine) and B9
(scheduler) are done as of 2026-08-28;
the B8 spike has Evolution API running in Compose and waits on the owner pairing the phone (OQ-1
open). Application code so far: the configuration boundary
(`specs/adr/0001-configuration-boundary.md`), the two models with their generated migrations, the
registration screens (forms, views, templates) and the admin now served under the secret segment
with the health endpoint outside it and the segment redacted on the logging path
(`specs/adr/0003-secret-path-and-log-redaction.md`), the structured logs with their correlation
keys and the audit entry every submission writes
(`specs/adr/0004-audit-and-structured-logging.md`), and the alert engine behind the provider
interface with its `send_alerts` command and scheduler service
(`specs/adr/0002-scheduler-container.md`).
On 2026-08-28 the owner revised foundation sections 3, 6 and 10, which opened B12 (service
catalogue), B13 (submitter identity), B14 (interface refactor) and B15 (alert state in the
interface); B16 (brand, theme control and the static pipeline) was opened and delivered the same
day. B12, B13, B14 and B16 are done: the catalogue and the submitter with their eleven migrations
(`specs/adr/0005-service-catalogue.md`, `specs/adr/0006-submitter-identity.md`), the first
administration registrations the project has, and the interface rebuilt responsive on a Radix token
system with the two combobox widgets the two fields use, and then the company lockup, a three
state theme control defaulting to the operating system, and whitenoise serving static under the
segment. B15 is the only open item of the four.
On 2026-08-31 the owner revised foundation section 6 to v0.2, which turned the path segment from
a credential into a short shareable link, and opened B17 (search and pages in the list) and B18
(the short link); both were delivered the same day, together with the loss of the `servicos/`
prefix on the list routes, so the screens are now `/novo/`, `/<pk>/vencimento/` and
`/<pk>/concluir/` under the segment and the segment floor in `deadliner/config.py` is three
characters.
Also on 2026-08-31 the owner took two decisions that move foundation section 3 and take the document
to v0.3: a service is registered by a start date and a term in days, with the due date derived from
the two and still stored (new section 3.3,
`specs/adr/0007-service-term-and-derived-due-date.md`, backlog B19), and the five services under
`Sustentabilidade e ESG` are withdrawn, so that category is deactivated and nothing is deleted
(section 3.2's dated note, backlog B20). B19, B20 and B15 are `doing` together on branch
`b15-b19-b20-alerts-term-and-catalogue`, in separate worktrees, and none of the three is verified
yet. What version 1 still owes: B10 (the CSV export), B15, B19, B20, the B8 adapter behind OQ-1 and
B11 behind OQ-2.
Stack, decided in the foundation: Python 3.13, Django 5.2 LTS with server-rendered templates and
Django Forms, SQLite on a Docker volume, a plain virtualenv with pip and pinned requirements files,
`mypy --strict` with django-stubs, ruff, pytest with pytest-django, Docker Compose from the first
commit, a justfile at the root. Pinned versions and what was learned confirming them live in
`specs/dependencies.md`. Authority chain: `specs/foundation.md` then this file then `specs/adr/`
then task specs. A contradiction between documents is a defect: stop and report, never reconcile
silently in code.

## What it is

An internal tool for Vale Verde Ambiental. A form (client, catalogue service, observation, start
date, term in days, submitter) writes flat records to SQLite; a daily engine computes which
warnings are owed and sends them to the company's WhatsApp number through a self-hosted Evolution
API instance; every submission is audited; the dataset exports to CSV. No login and, since the
owner decision of 2026-08-31, no secret either: the application is served under a short path
segment meant to be sent to people, so anyone holding or guessing it can read and write everything
(foundation section 6 v0.2). Do not write code that assumes the segment is unguessable, and do not
add an access control that the foundation does not decide. Django's admin, with the framework's
standard authentication, sits inside that segment as a maintenance door and is not the
employee-facing product.

The one idea everything derives from: the truth lives in persisted records. Every run derives
what is owed from the database and the injected current date, never from process memory, so a
crash or a missed day costs lateness at most, never a lost or duplicated warning.

## Repository layout

- Canon: `specs/foundation.md`, `specs/testing.md`, `specs/backlog.md` (delivery sequence and
  execution state, items B1 onward), `specs/dependencies.md`, `specs/log.md`, `specs/adr/README.md`,
  this file.
- Toolkit: `.claude/` (skills, hooks, settings; its index is `.claude/skills/README.md`).
- Code: `deadliner/` is the Django project (settings, config, urls, log_redaction, log_context,
  log_format, wsgi, asgi), `core/` is the app
  (`models.py` with `Service`, `Alert`, `ServiceCategory`, `CatalogService` and `Submitter`,
  `migrations/` generated by the CLI, `forms.py`, `views.py`
  including the health endpoint, `urls.py`, `templates/core/`, `admin.py`, `widgets.py` for the
  combobox widgets, `identity.py` for name normalization, `terms.py` for the due date derivation,
  `audit.py`, `engine.py` and `provider.py` for the daily engine,
  `management/commands/send_alerts.py`, `static/` with the brand assets), `manage.py` at the root.
  `tests/` holds every test; each names the identifier it implements.
  Styles and scripts are inline in `core/templates/core/_styles.html`, `_scripts.html` and
  `_theme.html`; `static/` is for vendored assets, and `staticfiles/` is the untracked
  `collectstatic` artifact.
- Tooling: `pyproject.toml` (tool configuration only), `requirements.txt` and
  `requirements-dev.txt` (pins), `justfile`, `Dockerfile`, `compose.yaml`, `.gitleaks.toml`,
  `.github/workflows/ci.yml`, `.env.example` (placeholder keys; the real `.env` is untracked).

Do not create folders for anything not yet decided.

## Non-negotiable constraints

Each cites its invariant in the foundation; the acceptance test lives there in full.

- **C1** (I1): at most one WhatsApp message per (service, threshold), enforced by a uniqueness
  rule on the persisted alert. Test: run the engine twice, observe one delivery per warning.
- **C2** (I2): a failed send lands in a visible failed state and is retried next run; no silent
  terminal state exists. Test: failing provider fake, then the interface shows the failure.
- **C3** (I3): owed warnings are computed from persisted records plus an injected clock; a run
  after missed days sends every never-sent warning once. Test: skip days, run once, each owed
  warning delivered exactly once.
- **C4** (I4): thresholds (30/7/0 days), destination number, message template and secret path are
  configuration, never literals. Test: two configs, two schedules, no code change.
- **C5** (I5): no secret in the repository, no production credential or data outside production.
  Test: the CI secret-scan gate passes and the real env file is untracked.
- **C6** (I6): every form submission emits a structured audit log with IP, Cloudflare country,
  timestamp, record id and submitter id. Test: POST with Cloudflare headers yields that entry.
- **C7** (I7): the path segment is redacted on the logging path. It guards little since the
  segment stopped being secret on 2026-08-31, and it stands until a decision removes it. Test:
  request a segment route, assert the segment is absent from captured logs.
- **C8** (I8): one person is one submitter row, however the name is spelled in case, accent or
  spacing, enforced by a uniqueness rule on the normalized name. Test: submit as `José Victor` and
  as `jose  victor`, observe one row and one id in both audit entries.

## Key behaviors to implement correctly

- "Today" is computed in America/Campo_Grande from an injected clock. A test that sleeps or reads
  the real clock inside a decision is a defect.
- The catch-up rule: for every active service and every configured threshold whose trigger date is
  on or before today, with no sent alert for that pair, send exactly one message, its text
  computed at send time from the current record. Late beats never.
- Warnings are computed only for services with status active. Completing a service or moving its
  deadline is a human action through the form.
- A deadline is a start date plus a term in days, and `due_date` stays a stored column derived by
  `Service.save` from the pure `due_date_from` in `core/terms.py` on every write. Never make it a
  property and never write it by hand: the daily run, the I1 uniqueness rule, the list ordering and
  the search all decide on it in the database, and moving a deadline means editing the two inputs
  (foundation section 3.3, `specs/adr/0007-service-term-and-derived-due-date.md`).
- What a service is comes from the catalogue, never from free text. A record references the
  catalogue service and never its category; subcategory is not an entity; a name is unique inside
  its category; a service the company stops offering is deactivated, never deleted, and both new
  foreign keys are `PROTECT` so a delete fails loudly instead of taking deadlines with it. The
  fifteen rows are seeded by a data migration and edited afterwards through the admin, because
  `choices=` on the field is the literal I4 forbids and the business renames services often. The
  `Sustentabilidade e ESG` category is deactivated since 2026-08-31, so its five services are not
  offered and the records already pointing at one are untouched.
- The submitter is a row, not a string. The typed name is normalized (NFKD strip, casefold,
  whitespace collapse) and resolved by get or create on that unique key, first spelling wins, and
  it authenticates nobody: it is a claim by an anonymous visitor that makes the audit trail
  countable (I8), never a login, and the IP and country stay beside it.
- The notification provider is a narrow interface with one operation (deliver text to the
  configured number, report acceptance). Evolution API is an adapter behind it. Tests fake the
  interface; never mock the vendor SDK, never call the network in a unit test.
- Client IP and country come from Cloudflare's forwarding headers only; that trust is part of the
  deployment contract (OQ-2).
- The health endpoint is the single route outside the secret path; it touches no dependency.
  The admin is inside the segment and keeps Django's own authentication (foundation section 6), and
  so is `STATIC_URL`, because assets at the site root would be a second route outside it.
- The UI is in Portuguese; code, tests, commits and documents are in English.
- Do not resolve OQ-1, OQ-2 or OQ-3 by inference. They are closed only as the foundation says.

## Testing and TDD

Test-first in two windows: Window A writes failing behaviour tests, Window B implements the
minimum to green and may not edit a test. Decisions (schedule computation, message rendering,
threshold evaluation) are pure functions carrying the bulk of the tests; effects (database,
clock, Evolution HTTP, logging) sit behind narrow interfaces with a real adapter and a test fake.
Every test names the constraint or requirement it implements. Full method: `specs/testing.md`.

## Standing rules

- Never assert about a document section you did not open in this window.
- Before using a library or external API, load its current documentation and confirm against the
  pinned version; findings go to `specs/dependencies.md`, never a comment. Never decide from
  memory (this is what keeps OQ-1 open).
- Framework-owned files (apps, migrations) are generated by the framework's CLI, then edited.
  Never hand-write a migration.
- Structural performance is not optional: the export and the daily run read in a constant number
  of queries, never one per row. Complexity-adding optimisation requires a measurement first.
- A comment exists only where correct code looks wrong; cite canon identifiers (I3, OQ-1), never
  restate their reasoning.
- A state claim ("tests pass") is written only with the command that verified it.
- A decision changed anywhere is propagated to every document carrying it in the same pass, and
  one line goes to `specs/log.md`.
- Prose rule: no em dashes, no en dashes, no double hyphens in prose, in any document, and
  everything under `specs/` and `.claude/` is English.
- Three rules are enforced by hooks in `.claude/hooks/`: the prose rule (`check-prose.sh`), no
  direct push touching `main` (`block-main-push.sh`), and no env file or SQLite database staged
  (`block-secrets.sh`, C5). The hooks need `jq` on the machine. The CI gates (ruff, mypy, pytest,
  secret scan) exist since B1 and must exist before the code they govern.
- Configuration has one boundary: `load_config` in `deadliner/config.py` parses and validates the
  whole environment, the settings module calls it once, nothing else reads `os.environ`, and
  application code takes the business values from `get_config()`. No business value has a default
  in code (I4), so `.env.example` carries the nine variables of this boundary plus the three
  `EVOLUTION_*` keys that only Compose reads; `just` loads `.env`, Compose passes it as
  `env_file`, CI sets non-secret values. Names, canonical forms and validation rules live in
  `specs/adr/0001-configuration-boundary.md`.

## Commands

All through `just` (it loads `.env` first). `just` with no argument lists them.

- `just setup`: create `venv/` with Python 3.13 (`py -3.13` on Windows, `python3.13` elsewhere),
  install `requirements-dev.txt`, copy `.env.example` to `.env` if absent, run `collectstatic`
  (whitenoise warns on every middleware construction without it).
- `just dev`: Django development server. `just manage <args>`: any `manage.py` command.
- `just lint` (ruff check and format check), `just format`, `just typecheck` (`mypy --strict`),
  `just test [args]` (pytest), `just secret-scan` (gitleaks over the working tree, needs Docker).
- `just gate`: lint, typecheck, test, secret-scan, in CI order. Green here is the precondition for
  a commit.
- `just up` / `just down`: the Compose stack (web on port 8000, the daily scheduler, SQLite on the
  `data` volume, Evolution API on 127.0.0.1:8080 with its own Postgres and Redis).
- `just evolution-up`, `evolution-status`, `evolution-instance`, `evolution-qr`, `evolution-state`,
  `evolution-send <number> <text>`: the B8 spike steps, in that order. Findings and pins:
  `specs/dependencies.md`, Evolution section.
