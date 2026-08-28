# Deadline Notification System, foundation

Status: active. Version 0.1, 2026-08-28.

This document is the single source of truth for this project. Every other document, including
`CLAUDE.md`, the ADRs and any future task spec, derives from it and loses to it on any disagreement.
It decides the what and the why. Code shape belongs to ADRs, and library versions belong to
`specs/dependencies.md` once one exists.

## 0. How to read this document

Three kinds of statement appear here, and they are not equal.

**Closed decisions** carry a Decision block with *What this buys* and *What this costs*. They are
reopened only through a logged revision in `specs/log.md`, never by a code change that quietly
disagrees.

**Invariants** (I1 onward) are properties that always hold. Each one becomes a pass/fail test.
Breaking one is a regression, never a tradeoff.

**Open questions** (OQ-1 onward) are explicitly not decided. They are closed by the thing named in
their entry, an owner answer or a spike with an exit criterion, and never by inference in a later
window.

Scope policy: this is an internal tool for one small company, Vale Verde Ambiental. Version 1 is
the registration form, the daily alert engine, the audit trail and the CSV export. There is no
delivery deadline stated in the brief, so "ship it sooner" is not an architectural argument here.

## 0.5. Product philosophy

Today the company tracks client service deadlines, environmental licenses and the like, in heads
and loose spreadsheets. A deadline that slips past unnoticed means an expired license, a fine, a
client harmed and trust lost. The person who suffers is the employee who was supposed to remember,
and the client who paid them to.

The product refuses to be a project management suite. It stores three facts per service, who the
client is, what the service is, when it is due, and it makes one promise: before that date arrives,
the company's WhatsApp receives a warning, and if the warning could not be delivered, a human can
see that it failed.

Its moral line: it never fails silently. A send that did not happen is a visible fact in the
system, never an absence.

The design rule worth quoting on its own: **a deadline the system knows about is a deadline
someone gets warned about, exactly once per warning.**

## 1. What it is

A small web application. A form with three fields (client, service, due date) writes flat records
into a local database. Once a day, an engine looks at every active record, decides which warnings
are owed, and sends them to the company's WhatsApp number through a self-hosted Evolution API
instance. Every submission is audited, every send attempt is recorded, and the whole dataset
exports to a spreadsheet in one click. The audience is the employees of one company, reachable
through a private link with no login.

## 2. The core thesis

The question a system like this must answer first: where does the truth about what happened live,
and what happens when WhatsApp does not answer?

**Decision.** The truth lives in the database, in persisted records, and nowhere else. The due
date lives in a record. Whether a given warning was sent, and when, and whether it failed, lives in
a record. The daily run derives everything it does from those records and from the injected
current date, never from process memory, a queue, or the memory of a previous run. Sending a
WhatsApp message is an effect whose outcome is written back before anything else depends on it.

*What this buys:* the machine can be off for a weekend, the container can restart mid-run, the
Evolution instance can be down for a day, and the next successful run still sends every warning
that is owed, exactly once, because owed-ness is computed from what is persisted. No warning is
lost to a crash and none is duplicated by a retry.

*What this costs:* every send attempt does a database write before and after, and the alert table
grows forever. At this company's scale, hundreds of records, that cost is noise.

Rejected alternatives: an in-memory scheduler (dies with the process), a message queue with
delayed delivery (infrastructure this scale does not justify, and the queue would become a second
place where truth lives), sending at registration time for future delivery (same flaw).

## 3. Data model and its frontier

**Decision.** One flat record per service: client name (text), service description (text), due
date, status (active or completed), created timestamp. No separate client table, no foreign keys
between business entities in version 1. Alongside it, one alert record per warning attempt,
carrying the service it belongs to, which threshold it implements, its state and its timestamps.

*What this buys:* the brief demands a structure simple enough to export to a spreadsheet, and a
flat record is a spreadsheet row by construction. The form stays three fields. Migration to a
normalized client table later is a mechanical data migration, not a redesign.

*What this costs:* the same client typed twice is two strings, with no deduplication. The future
employee-facing WhatsApp query feature will likely want a real client entity; that is version 2
paying for version 1's simplicity, and it is the right direction to defer.

Status is the whole lifecycle in version 1. A renewed or delivered service is marked completed by
a human, or its due date is edited by a human. Warnings are computed only for active services.
Recurrence and automatic renewal are non-goals (see section 10).

## 4. The WhatsApp integration

Evolution API is the vendor. No instance exists yet, so hosting one is part of this project: it
runs as a neighboring service in the same Docker Compose stack, opaque to the application, with
its own internal dependencies belonging to it and not to us (OQ-1 covers its exact footprint).

**Decision.** The application talks to a notification provider through a narrow interface sized by
what the product needs, which is one operation: deliver this text to the configured company
number, and tell me whether you accepted it. Evolution API is one adapter behind that interface.
Tests use a fake of the interface, never a mock of the vendor.

*What this buys:* the entire alert engine is testable without a network, and if Evolution API is
ever replaced, one adapter changes.

*What this costs:* a thin layer of indirection for a single vendor. It is the standing rule of the
method and it costs a file.

Failure modes, decided from the brief's purpose: a rejected or errored send puts the alert record
into a failed state that a human can see in the interface. The next daily run picks up failed and
never-attempted alerts alike, because both are simply alerts that are owed and not sent. There is
no silent terminal state (I2), and no alert is delivered twice (I1).

The company's destination number already exists and is configuration, never a literal (I4). The
message template, Portuguese text with the client, service, due date and days remaining, is also
configuration; its exact wording is OQ-3.

## 5. Timing and scheduling

**Decision.** Three warnings per service: 30 days before the due date, 7 days before, and on the
due date itself. Each is sent exactly once per service. The thresholds are data in versioned
configuration, not code. A service registered inside a window receives only the warnings whose
trigger date has not passed, plus catch-up as below.

*What this buys:* a deterministic, testable rule that matches the brief's "about a week or a
month". Changing the cadence is a config edit.

*What this costs:* no per-service custom cadence in version 1. If a service type ever needs its
own rule, that is a logged revision.

**Decision.** The engine is a Django management command executed once a day by a scheduler that
lives in the Compose stack, outside the web process. No Celery, no Redis, no queue.

*What this buys:* zero extra infrastructure. Daily granularity is exact for thresholds measured
in days.

*What this costs:* nothing intraday can be sent. For this product that is not a loss.

Catch-up rule: at each run, for every active service and every configured threshold whose trigger
date is on or before today, with no sent alert for that pair, one alert is sent, with the message
computed at send time from the current record. If runs were missed, warnings arrive late rather
than never (I3). "Today" is computed in the America/Campo_Grande timezone from an injected clock.

## 6. Access, identity and audit

**Decision.** There is no login. The application is reachable only by employees who hold the link:
the entire application is served under a secret path segment held in configuration, behind
Cloudflare, and it asks no one who they are. A health endpoint used by the container runtime is
the single route outside the secret path, and it touches no dependency and reveals no data.

*What this buys:* zero-friction use by a small trusted team, exactly as the owner decided.

*What this costs:* anyone holding the link can read and write everything. The link is a
credential: it must never enter the repository, and if it leaks the remedy is rotating the
configured path, which breaks saved bookmarks. Because request paths normally appear in logs, the
secret would leak into its own audit trail; redaction of the secret segment lives on the logging
path (I7).

**Decision.** Every form submission is audited: a structured log entry with the submitter's IP,
their country as reported by Cloudflare, the timestamp, and the identifier of the record touched.
The client IP and country are taken from Cloudflare's forwarding headers, which are trustworthy
only because all traffic arrives through Cloudflare; that arrangement is part of the deployment
contract (OQ-2).

*What this buys:* the minimum observability the owner asked for, who sent what and when, without
accounts.

*What this costs:* attribution is to a network address, never to a person. The owner accepted
that.

## 7. Export

**Decision.** A CSV export button in version 1, producing one row per service record with every
business field. *What this buys:* it proves the flatness promise of section 3 continuously, and it
is the owner's stated need. *What this costs:* nearly nothing; it is a single streamed query.

## 8. Architecture and stack

Python 3.13, Django 5.2 LTS with server-rendered templates and Django Forms, SQLite on a Docker
volume (the brief's explicit choice, overriding the PostgreSQL default), a plain virtualenv with pip
and pinned requirements files for packaging (owner decision of 2026-08-28, replacing uv; see section
13), `mypy --strict` with django-stubs, ruff, pytest with pytest-django, a justfile at the root.
Containerised from the first commit: one command brings up the whole stack, and development and
deployment differ in configuration, never in architecture.

The Compose stack runs the web application, the daily scheduler, and the Evolution API service
with whatever internal dependencies OQ-1 confirms it needs. Cloudflare fronts the public
hostname; the mechanism (Tunnel versus proxied DNS) is OQ-2. Configuration comes from the
environment; no secret enters the repository and no production credential or data exists in a
non-production environment (I5).

Performance rule: the dataset is tiny, so structural performance is simply not writing the
defect, the export and the daily run each read the database in a constant number of queries,
never one per row. Any optimisation that adds complexity is bought with a measurement, and at
this scale none is expected, ever.

Observability rule: logs are structured and carry their correlation keys (request id, service id,
alert id), bound once per request or run. The audit fields of section 6 are on the logging path;
so is the redaction of the secret path segment. Liveness touches no dependency. No telemetry
vendor is chosen in application code.

## 9. Non-negotiable invariants

**I1. One warning, one message.** For a given service and threshold, at most one WhatsApp message
is ever delivered, by construction of a uniqueness rule on the persisted alert, never by the
engine remembering. Acceptance test: run the daily engine twice on the same day against the same
records; the provider fake records exactly one delivery per owed warning. Scar (design
reasoning): a retry after a partial failure, or an operator running the command by hand while the
scheduler also fires, would otherwise message the company phone twice and teach everyone to
ignore it.

**I2. Nothing fails silently.** A send attempt that does not succeed leaves the alert in a failed
state visible in the interface, and the state machine has no terminal state that a human cannot
see. Acceptance test: with the provider fake rejecting, run the engine; the interface lists the
alert as failed, and the next run attempts it again. Scar (from the brief): the product exists
because silent forgetting is the failure mode of the current spreadsheet.

**I3. The schedule survives death.** Which warnings are owed is computed from persisted records
and the injected current date, never from process memory, and a run after missed days sends
exactly the never-sent warnings whose trigger date has passed. Acceptance test: create records,
advance the injected clock past two thresholds with no runs, run once; both warnings are sent
once each. Scar (design reasoning): a host that is off over a weekend, or a crashed container,
must cost lateness at most, never a lost warning.

**I4. Business values are data.** Thresholds, the destination number, the message template and
the secret path live in versioned configuration, never as literals in code. Acceptance test: a
unit test computes the owed warnings under two different threshold configurations and observes
different schedules with no code change. Scar (prior art): a threshold buried in a function is
found by the person editing the wrong copy of it.

**I5. No secret in the repository, no production data outside production.** Acceptance test: an
automated secret scan runs as a CI gate and passes, and the environment file carrying real
credentials is untracked by construction. Scar (prior art): a committed credential outlives every
attempt to delete it from history.

**I6. Every write is attributed.** Each form submission produces a structured audit entry with
IP, Cloudflare-reported country, timestamp and the record identifier. Acceptance test: a POST
carrying Cloudflare forwarding headers yields a log entry containing those four fields.
Scar (owner decision, 2026-08-28): with no login, the audit trail is the only answer to "who
entered this".

**I7. The link never leaks into its own logs.** The secret path segment is redacted on the
logging path before any log line is written. Acceptance test: make a request to a secret-path
route, capture the emitted logs, assert the configured segment is absent. Scar (design
reasoning): access logs are the most copied, pasted and shipped-to-third-parties artifact a web
app produces, and the secret would otherwise ride along.

## 10. Explicit non-goals

Version 1 does not include: user accounts, roles or per-person attribution; a dashboard of
expiring services (named by the owner as the version 2 goal); an inbound WhatsApp API for
employees to query open clients (a version 3 idea in the brief); recurrence or automatic renewal
of services; multiple destination numbers; editing history or soft deletes; multi-company
tenancy; any report beyond the CSV export. Each of these is deferred, and adding one is a logged
revision that must argue against this line, never a quiet commit.

## 11. Open questions

**OQ-1. Evolution API self-hosting footprint.** Which image, which version, and which internal
dependencies (its own database, its own cache) the instance needs. Open because the method
forbids choosing this from memory. Closed by a spike whose exit criterion is a running Compose
stack that delivers one real message to the company number, with findings recorded in
`specs/dependencies.md`. Blocks the Compose entries for the Evolution service and the adapter's
integration test.

**OQ-2. Deployment host and Cloudflare mechanism.** Which always-on machine runs the stack, and
whether Cloudflare fronts it via Tunnel or proxied DNS. Open because the owner has not named the
host. Closed by an owner decision. Blocks deployment configuration only; application code is
indifferent to it, though I6's trust in Cloudflare headers assumes it is honoured.

**OQ-3. Message wording.** The Portuguese template text for each warning. Open because it is the
owner's voice, not a technical choice. Closed by the owner writing or approving the template.
Blocks nothing structural; a placeholder template satisfies every test.

## 12. Development method

The method, test-first in two windows, decisions kept pure and effects behind narrow interfaces,
the clock injected everywhere, lives in `specs/testing.md` and binds every implementation window.

## 13. Decision log and revisions

2026-08-28, foundation v0.1. Closed: core thesis (persisted truth, derived schedule); flat data
model; provider interface with self-hosted Evolution API; thresholds 30/7/0 as config; daily
management command, no queue; no login, secret link, Cloudflare front; IP, country and time
audit; CSV export in v1; SQLite per the brief. Opened: OQ-1, OQ-2, OQ-3. Owner answers of
2026-08-28 (no login, Cloudflare, audit fields, no Evolution instance yet, number exists) are
incorporated above.

2026-08-28, revision during B1. Section 8 packaging changed from uv to a plain virtualenv with pip
and pinned requirements files, by owner decision ("keep it simple"). What this buys: no extra tool
to install, the standard Python workflow. What this costs: no lockfile, so transitive versions are
pinned only through the direct pins recorded in `specs/dependencies.md`.
