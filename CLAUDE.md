# CLAUDE.md

This file is a digest. The single source of truth is `specs/foundation.md`; when the two disagree,
the foundation wins and this file is the one that is wrong. Fix this file, never code against it.

## Project status

B1 (scaffold) and B2 (configuration surface) are done as of 2026-08-28. The only application code
is the configuration boundary, whose shape is `specs/adr/0001-configuration-boundary.md`.
Stack, decided in the foundation: Python 3.13, Django 5.2 LTS with server-rendered templates and
Django Forms, SQLite on a Docker volume, a plain virtualenv with pip and pinned requirements files,
`mypy --strict` with django-stubs, ruff, pytest with pytest-django, Docker Compose from the first
commit, a justfile at the root. Pinned versions and what was learned confirming them live in
`specs/dependencies.md`. Authority chain: `specs/foundation.md` then this file then `specs/adr/`
then task specs. A contradiction between documents is a defect: stop and report, never reconcile
silently in code.

## What it is

An internal tool for Vale Verde Ambiental. A three-field form (client, service, due date) writes
flat records to SQLite; a daily engine computes which warnings are owed and sends them to the
company's WhatsApp number through a self-hosted Evolution API instance; every submission is
audited; the dataset exports to CSV. No login: access is a secret link behind Cloudflare.

The one idea everything derives from: the truth lives in persisted records. Every run derives
what is owed from the database and the injected current date, never from process memory, so a
crash or a missed day costs lateness at most, never a lost or duplicated warning.

## Repository layout

- Canon: `specs/foundation.md`, `specs/testing.md`, `specs/backlog.md` (delivery sequence and
  execution state, items B1 onward), `specs/dependencies.md`, `specs/log.md`, `specs/adr/README.md`,
  this file.
- Toolkit: `.claude/` (skills, hooks, settings; its index is `.claude/skills/README.md`).
- Code: `deadliner/` is the Django project (settings, config, urls, wsgi, asgi), `core/` is the app,
  `manage.py` at the root. `tests/` holds every test; each names the identifier it implements.
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
  timestamp and record id. Test: POST with Cloudflare headers yields that entry.
- **C7** (I7): the secret path segment is redacted on the logging path. Test: request a
  secret-path route, assert the segment is absent from captured logs.

## Key behaviors to implement correctly

- "Today" is computed in America/Campo_Grande from an injected clock. A test that sleeps or reads
  the real clock inside a decision is a defect.
- The catch-up rule: for every active service and every configured threshold whose trigger date is
  on or before today, with no sent alert for that pair, send exactly one message, its text
  computed at send time from the current record. Late beats never.
- Warnings are computed only for services with status active. Completing a service or editing its
  due date is a human action through the form.
- The notification provider is a narrow interface with one operation (deliver text to the
  configured number, report acceptance). Evolution API is an adapter behind it. Tests fake the
  interface; never mock the vendor SDK, never call the network in a unit test.
- Client IP and country come from Cloudflare's forwarding headers only; that trust is part of the
  deployment contract (OQ-2).
- The health endpoint is the single route outside the secret path; it touches no dependency.
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
  in code (I4), so `.env.example` carries all nine variables; `just` loads `.env`, Compose passes
  it as `env_file`, CI sets non-secret values. Names, canonical forms and validation rules live in
  `specs/adr/0001-configuration-boundary.md`.

## Commands

All through `just` (it loads `.env` first). `just` with no argument lists them.

- `just setup`: create `venv/`, install `requirements-dev.txt`, copy `.env.example` to `.env` if
  absent.
- `just dev`: Django development server. `just manage <args>`: any `manage.py` command.
- `just lint` (ruff check and format check), `just format`, `just typecheck` (`mypy --strict`),
  `just test [args]` (pytest), `just secret-scan` (gitleaks over the working tree, needs Docker).
- `just gate`: lint, typecheck, test, secret-scan, in CI order. Green here is the precondition for
  a commit.
- `just up` / `just down`: the Compose stack (web on port 8000, SQLite on the `data` volume).
