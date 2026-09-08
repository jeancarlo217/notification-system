# Deadline Notification System, foundation

Status: active. Version 0.4, 2026-09-02.

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

**Version 1 ships in two phases, by owner decision of 2026-08-31.** Phase one is the registration
form, the audit trail and the CSV export, and it is live. Phase two is the daily alert engine
reaching WhatsApp, which waits on OQ-1. The reason is the owner's and it is a good one: there is
nothing worth notifying anybody about until the registry has something in it, so the engine is
built, tested and not deployed rather than deployed and useless. Nothing about the scope of version
1 changed; only the order in which it arrives.

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

A small web application. A form writes flat records into a local database: who the client is,
which service from the catalogue of section 3.1, when it starts and how many days it runs, an
optional observation, and who is entering it. Once a day, an engine looks at every active record,
decides which warnings are owed, and sends them to the company's WhatsApp number through a
self-hosted Evolution API instance. Every submission is audited, every send attempt is recorded,
and the whole dataset exports to a spreadsheet in one click. The audience is the employees of one
company, reachable through a short shared link with no login.

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

**Decision.** One flat record per service: client name (text), the service chosen from the
catalogue of section 3.1, an optional free text observation, the start date and the term in days of
section 3.3 with the due date derived from them, status (active or completed), created timestamp,
and the submitter of section 6. The client is still a bare string,
so there is still no client table. The only foreign keys a service record carries point at the two
reference entities, the catalogue entry and the submitter; no service record points at another.
Alongside it, one alert record per warning attempt, carrying the service it belongs to, which
threshold it implements, its state and its timestamps.

*What this buys:* the brief demands a structure simple enough to export to a spreadsheet, and a
flat record is a spreadsheet row by construction. A reference to a catalogue entry resolves to one
column on the way out, so the promise survives the reference. Migration to a normalized client
table later is a mechanical data migration, not a redesign.

*What this costs:* the same client typed twice is two strings, with no deduplication. The future
employee-facing WhatsApp query feature will likely want a real client entity; that is version 2
paying for version 1's simplicity, and it is the right direction to defer.

Status is the whole lifecycle in version 1. A renewed or delivered service is marked completed by
a human, or its deadline is moved by a human editing the start date or the term of section 3.3.
Warnings are computed only for active services. Recurrence and automatic renewal are non-goals
(see section 10).

### 3.1. The service catalogue

**Decision (owner, 2026-08-28).** What a service is stops being free text and becomes a choice from
a catalogue held in the database: a category, and a service inside it. The catalogue is the one the
company declares in July 2026, three categories and fifteen services, reproduced in section 3.2.
The employee picks one, and the free text that used to name the service becomes an optional
observation beside it, for the detail the catalogue cannot express.

The catalogue is data, not code. It is two tables, seeded once with the declaration below and
edited afterwards through the administration site of section 6. It is never an enumeration of
choices compiled into a field, because the company renames and reorders its services and each
rename would otherwise be a schema migration. The catalogue changing often is a property of the
business, not an accident to be designed against.

Four rules the catalogue obeys, taken from the sister project Ecobalance so that the two lists can
be joined later without a redesign:

1. A service record references the catalogue service, never its category. Category is navigation,
   and reorganising a menu must never touch a tracked deadline.
2. Subcategory does not exist as an entity. A service that needs a contractable subdivision is born
   as more services.
3. A name is unique inside its category, and a service the company stops offering is deactivated,
   never deleted, because deadlines already point at it.
4. Each catalogue row reserves a column for the identifier Ecobalance will one day assign it, so
   the switch from a local copy to a consumed list is a backfill rather than a rewrite.

*What this buys:* a fixed vocabulary. Fifteen service names typed by two people in twelve different
spellings are fifteen unqueryable strings, and the version 2 dashboard is impossible on top of
them. It also makes the field a select, which is faster to fill than a text box and cannot be
misspelled.

*What this costs:* a service the catalogue does not carry cannot be registered until somebody adds
it, which is friction on purpose. The two tables are also a copy of a list Ecobalance will
eventually own; the reserved column of rule 4 is what keeps that copy cheap to retire.

The names in the catalogue are Portuguese because they are data shown to the user, not identifiers.
Code, keys and column names stay English, per section 12.

### 3.2. The catalogue as the company declares it, July 2026

| Category | Service |
| --- | --- |
| Regularização e Licenciamento | Licenciamentos Ambientais |
| Regularização e Licenciamento | Cadastro Ambiental Rural (CAR) |
| Regularização e Licenciamento | Corte de Árvores Nativas (CANI) |
| Regularização e Licenciamento | Regularização Fundiária |
| Regularização e Licenciamento | Ratificação: Faixa de Fronteira |
| Regularização e Licenciamento | Outorga de Recursos Hídricos |
| Geotecnologias | Georreferenciamento |
| Geotecnologias | Sensoriamento Remoto |
| Geotecnologias | Agricultura de Precisão |
| Geotecnologias | Projetos de Drenagem |
| Sustentabilidade e ESG | Diagnóstico Global ESG |
| Sustentabilidade e ESG | Inventário de GEE |
| Sustentabilidade e ESG | Levantamento de Estoque de Carbono |
| Sustentabilidade e ESG | Planos de Descarbonização |
| Sustentabilidade e ESG | Geração de Créditos de Carbono |

This table is the business declaration of July 2026, not a production table: Ecobalance's own
`catalog/` package does not exist yet and its 1.0 list lives only in a production database that by
rule is not on any development disk. Its question SRV-1, asking the business to confirm the current
categories and services, is still open there. So this table is what to build against, and a later
correction from the business is an edit through the administration site, never a schema migration.
When the company adds or withdraws a service for good, the seeding of section 3.1 is amended by a
data migration in the same pass, so a database created afterwards comes up in the same state as the
one already running.

**Note, 2026-08-31 (owner).** The company no longer performs the five services under
`Sustentabilidade e ESG`, so that category is deactivated. The rows stay in the table above because
the table is the July 2026 declaration and a withdrawal is not recorded by rewriting what the
business said in July. Rule 3 of section 3.1 governs what happens in the database: a service the
company stops offering is deactivated and never deleted, both catalogue foreign keys are `PROTECT`,
and a tracked record already points at `Inventário de GEE`, so a delete would either fail loudly or
take a deadline with it. Deactivating the category hides its five services from the registration
form and hides nothing else, so records already pointing at one keep listing, keep being editable
and keep earning their warnings. Delivery is backlog B20.

### 3.3. The service term

**Decision (owner, 2026-08-31).** A service is no longer registered by typing the date it is due.
The employee types the date it starts and a term in days, and the deadline is the first plus the
second: a service starting on the 5th with a term of twenty days is due twenty days after the 5th.
Both facts are stored on the record. The due date survives as a stored field, derived from those
two on every write, and it stays what the thresholds of section 5 and the warnings of section 4
measure against, so nothing downstream of the record learns a new rule.

*What this buys:* the way the business already thinks about a deadline. A term counted from a date
is what the contract says and what the employee has in front of them; the due date was arithmetic
they were doing in their head at the keyboard, and a system that makes a person compute a value it
could compute itself is eventually handed a wrong one. Two facts the employee holds become two
facts the record holds, so a term that turns out to be wrong is corrected as a term rather than
reverse engineered out of a date.

*What this costs:* a value derived into a column can disagree with the inputs it came from, which a
value computed on the way out never can. The rule that keeps them in step now lives on the write
path, so every door into the record, the form, the administration site, a migration, an import, has
to go through it, and the administration site shows the due date read only for that reason.
Existing rows also carry a term the system does not know: they are backfilled with the start date
set to the due date they already had and a term of zero, which preserves every due date exactly, so
no alert changes state and no warning fires twice or goes missing (I1, I3). The price of that is a
stored term that is honestly wrong for those rows until a human corrects it, and the alternative,
inventing a plausible term, would be a guess wearing the clothes of a fact.

The field names in code are `start_date` and `term_days`. The Portuguese labels the interface shows
are `Data de início` and `Prazo (dias)`, and the owner has not settled that wording; a label is one
line to change and a field name is not, which is the same distinction this project recorded on
2026-08-28 for the B12 and B13 fields. Code shape, including why the due date stays a column and
does not become a computed attribute, is `specs/adr/0007-service-term-and-derived-due-date.md`.
Delivery is backlog B19.

## 4. The WhatsApp integration

Evolution API is the vendor. No instance exists yet, so hosting one is part of this project: it
runs as a neighboring service in the same Docker Compose stack, opaque to the application, with
its own internal dependencies belonging to it and not to us (OQ-1 covers its exact footprint).

**Decision.** The application talks to a notification provider through a narrow interface sized by
what the product needs, which is one operation: deliver this text to the configured destination,
and tell me whether you accepted it. Evolution API is one adapter behind that interface.
Tests use a fake of the interface, never a mock of the vendor.

*What this buys:* the entire alert engine is testable without a network, and if Evolution API is
ever replaced, one adapter changes.

*What this costs:* a thin layer of indirection for a single vendor. It is the standing rule of the
method and it costs a file.

Failure modes, decided from the brief's purpose: a rejected or errored send puts the alert record
into a failed state that a human can see in the interface. The next daily run picks up failed and
never-attempted alerts alike, because both are simply alerts that are owed and not sent. There is
no silent terminal state (I2), and no alert is delivered twice (I1).

**Decision, owner, 2026-09-02: the destination is a WhatsApp group, held in one configuration
variable.** The warnings land in a group the company's own people are in, not in one person's
chat, and the variable that names it is the single destination the product has (I4). It accepts
either a group identifier or a plain number, because the two differ only in the string that goes
into the same field, and one variable cannot be ambiguous about which destination wins.

*What this buys:* the people who act on a deadline see it at the same moment, and nobody is the
single point of failure for reading the phone. *What this costs:* everyone in the group sees every
client name and service, which is a disclosure inside the company and has to be an accepted one;
and the group identifier is not typed by a human, it is read from the vendor once and pasted into
configuration, so a group that is deleted and recreated is a configuration change.

The sender is the company's own WhatsApp Business account, paired to the self-hosted instance, and
it has to be a member of the group. Section 8's stack owns that pairing; OQ-1 covers it.

**Decision, owner, 2026-09-02: one run sends one message, a list of what is expiring.** The daily
run does not send one message per warning. It renders every warning owed today as one line
carrying the client, the service and the days remaining, and delivers the whole list as a single
message. A run that owes nothing sends nothing. When one service owes more than one threshold in
the same run, which the catch-up rule of section 5 makes possible, it takes one line and every
owed pair behind it is recorded as sent, so no service is listed twice in one message.

*What this buys:* a person reads one message and sees the whole day, which is what a warning is
for, and the burst the two phase decision predicted becomes one long message instead of fifty
short ones. *What this costs:* a failed send fails the whole list rather than one warning, which
I2 already handles by retrying every unsent warning in the next run's list, and the message can
grow long enough to be scrolled on the first run after a backlog of deadlines.

The destination and the templates are configuration, never literals (I4). The Portuguese text,
both the line and whatever heads the list, is still the owner's voice and still OQ-3.

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
date is on or before today, with no sent alert for that pair, one alert is owed, and every alert
owed by that run is delivered together as the single message of section 4, its text computed at
send time from the current records. If runs were missed, warnings arrive late rather
than never (I3). "Today" is computed in the America/Campo_Grande timezone from an injected clock.

## 6. Access, identity and audit

**Decision.** There is no login. The application is reachable only by employees who hold the link:
the entire application is served under a secret path segment held in configuration, behind
Cloudflare, and it asks no one who they are. A health endpoint used by the container runtime is
the single route outside the secret path, and it touches no dependency and reveals no data.

*What this buys:* zero-friction use by a small trusted team, exactly as the owner decided.

Static assets are served under the segment too, for the same reason: putting them at the site root
would create a second route outside it. The health endpoint stays the only one.

*What this costs:* anyone holding the link can read and write everything. Until 2026-08-31 that
cost was narrowed by making the link unguessable, and the owner decision below removed that
narrowing, so today it is the whole cost. The segment still never enters the repository, and
rotating it still breaks every saved bookmark. Because request paths normally appear in logs, the
segment would otherwise land in its own audit trail; redaction of it lives on the logging path
(I7).

**Decision (owner, 2026-08-28).** Django's own administration site stays, with the framework's
standard authentication, mounted inside the secret path segment. It is a maintenance door for the
owner and the developers, never the employee-facing product: the form, the list and the lifecycle
actions of section 1 ask no one who they are and never send anybody to a login screen.

*What this buys:* a way to read and repair records without building a screen for it, using the
framework's own account and permission machinery instead of a hand-written one. Two barriers guard
that door, the link and a password, because it sits inside the segment.

*What this costs:* `django.contrib.auth` and its user accounts now exist in the system, so the
non-goal of section 10 narrows to the employee-facing application. A login form inside the secret
path is still a login form, reachable by anyone holding the link, so its accounts belong to the
owner and the developers and never to one employee each.

**Decision (owner, 2026-08-28).** The registration form asks who is entering the record. The field
offers the people who already registered something, starting with José Victor and Geovanna who
enter most of them, and it also accepts a name nobody anticipated, typed as plain text and saved as
typed. One person is one row however their name is spelled: differences of case, accent and spacing
resolve to the same submitter, so the audit trail counts them once (I8).

*What this buys:* the audit trail finally answers "who entered this" with a name. Attribution by
network address alone told the owner which router the record came through, which is not an answer.

*What this costs:* the name is a claim, not a credential. Anyone holding the link can type any
name, including somebody else's, and two employees who genuinely share a name are one row. This is
useful attribution, never evidential attribution, and section 10 is revised in the same pass so
that nobody reads it as the start of user accounts.

**Decision (owner, 2026-08-31).** The path segment is short and shareable, not secret. It is
chosen to be sent in a message and typed by hand, so a value such as `vale` is valid and the
configuration boundary lowers its floor from sixteen characters to three. Nothing takes its place:
no login, no check at the edge, no list of allowed addresses.

*What this buys:* one short address that reaches every employee through the channels the company
already uses, which is what the owner's management asked for.

*What this costs:* the application is open. Anyone who holds the link, is forwarded it, or guesses
it can read every client, every deadline and every submitter name, and can register, edit and
complete records. The company name and the words the tool is about are the first guesses anybody
makes. The audit trail of this section still records what was done and from which address, and it
still cannot say who did it, so with an open link it is a record of damage rather than a control
that prevents it. The owner was shown this consequence in full on 2026-08-31, with Cloudflare
Access and an application login offered as the two alternatives that also give a short address,
and chose the open link.

I7 is untouched by this: the segment is still redacted on the logging path. It now protects little,
and it stays because removing an invariant is its own decision and nobody has taken it.

**Decision.** Every form submission is audited: a structured log entry with the submitter's IP,
their country as reported by Cloudflare, the timestamp, the identifier of the record touched and
the submitter it belongs to.
The client IP and country are taken from Cloudflare's forwarding headers, which are trustworthy
only because all traffic arrives through Cloudflare; that arrangement is part of the deployment
contract (OQ-2).

*What this buys:* the minimum observability the owner asked for, who sent what and when, without
accounts.

*What this costs:* the address is observed and the name is asserted, and the entry carries both
because they fail in different directions. The owner accepted that.

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
hostname; the mechanism is Tunnel, decided on 2026-08-31 when OQ-2 closed, and until that zone
moves the host's own nginx stands in that place. Configuration comes from the
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

**I1. One warning, one delivery.** A given service and threshold is carried by at most one
delivered WhatsApp message, ever, by construction of a uniqueness rule on the persisted alert,
never by the engine remembering. Since the digest decision of section 4 a message carries many
warnings, so the guarantee is about the warning and not about the message: no warning appears in
two delivered messages, and no service appears twice in one. Acceptance test: run the daily engine
twice on the same day against the same records; the provider fake records one message on the first
run, listing each owed warning once, and no message at all on the second. Scar (design reasoning):
a retry after a partial failure, or an operator running the command by hand while the scheduler
also fires, would otherwise warn the group twice and teach everyone to ignore it.

**I2. Nothing fails silently.** A send attempt that does not succeed leaves the alert in a failed
state visible in the interface, and the state machine has no terminal state that a human cannot
see. A rejected message fails every warning it carried, since none of them reached anybody.
Acceptance test: with the provider fake rejecting, run the engine; the interface lists every alert
the message carried as failed, and the next run lists them again. Scar (from the brief): the product exists
because silent forgetting is the failure mode of the current spreadsheet.

**I3. The schedule survives death.** Which warnings are owed is computed from persisted records
and the injected current date, never from process memory, and a run after missed days sends
exactly the never-sent warnings whose trigger date has passed. Acceptance test: create records,
advance the injected clock past two thresholds with no runs, run once; both warnings are sent
once each. Scar (design reasoning): a host that is off over a weekend, or a crashed container,
must cost lateness at most, never a lost warning.

**I4. Business values are data.** Thresholds, the alert destination, the message templates and
the secret path live in versioned configuration, never as literals in code. Acceptance test: a
unit test computes the owed warnings under two different threshold configurations and observes
different schedules with no code change. Scar (prior art): a threshold buried in a function is
found by the person editing the wrong copy of it.

**I5. No secret in the repository, no production data outside production.** Acceptance test: an
automated secret scan runs as a CI gate and passes, and the environment file carrying real
credentials is untracked by construction. Scar (prior art): a committed credential outlives every
attempt to delete it from history.

**I6. Every write is attributed.** Each form submission produces a structured audit entry with
IP, Cloudflare-reported country, timestamp, the record identifier and the submitter identifier.
Acceptance test: a POST carrying Cloudflare forwarding headers yields a log entry containing those
five fields. Scar (owner decision, 2026-08-28): with no login, the audit trail is the only answer
to "who entered this".

**I7. The link never leaks into its own logs.** The secret path segment is redacted on the
logging path before any log line is written. Acceptance test: make a request to a secret-path
route, capture the emitted logs, assert the configured segment is absent. Scar (design
reasoning): access logs are the most copied, pasted and shipped-to-third-parties artifact a web
app produces, and the secret would otherwise ride along.

**I8. One name, one person.** Two submissions naming the same person resolve to one submitter
record, however that name is spelled in case, accent or spacing, by construction of a uniqueness
rule on a normalized form of the name. Acceptance test: submit once as `José Victor` and once as
`jose  victor`; exactly one submitter row carries that name, the number of submitter rows is
unchanged by the second submission, and both audit entries carry that row's identifier.
Scar (owner decision, 2026-08-28): a free text name field with no identity behind it produces four
spellings of one employee within a month, and an audit trail that cannot count people is not an
audit trail.

## 10. Explicit non-goals

Version 1 does not include: user accounts or roles in the employee-facing application, whose
administration site is the exception decided in section 6; authenticated attribution of any kind,
the self declared submitter name of section 6 being a claim by an anonymous visitor and never a
login; per action attribution, since the submitter belongs to the record and an edit does not ask
again; a dashboard of
expiring services (named by the owner as the version 2 goal); an inbound WhatsApp API for
employees to query open clients (a version 3 idea in the brief); recurrence or automatic renewal
of services; multiple destination numbers; editing history or soft deletes; multi-company
tenancy; any report beyond the CSV export. Each of these is deferred, and adding one is a logged
revision that must argue against this line, never a quiet commit.

## 11. Open questions

**OQ-1. Evolution API self-hosting footprint.** Which image, which version, and which internal
dependencies (its own database, its own cache) the instance needs. Open because the method
forbids choosing this from memory. Closed by a spike whose exit criterion is a running Compose
stack that delivers one real message to the destination group of section 4, with findings recorded
in `specs/dependencies.md`. Since the destination decision of 2026-09-02 the criterion names the
group and not a number, because a send that works to a person proves nothing about a send to a
group. Blocks the Compose entries for the Evolution service and the adapter's integration test.

**OQ-2. Deployment host and Cloudflare mechanism.** **Closed 2026-08-31 by owner decision.** The
host is a VPS the owner already runs, named on 2026-08-28, reachable over SSH. Cloudflare fronts it
by **Tunnel**, decided on 2026-08-31 with proxied DNS offered as the alternative: `cloudflared` runs
as a service in the same Compose stack of section 8, the machine opens no inbound port, and the
origin is therefore unreachable except through Cloudflare by construction rather than by a firewall
rule somebody has to maintain. That is what I6 needs, because the audit trail's IP and country come
from Cloudflare's forwarding headers and a request that reaches the origin directly can forge them.
The application is reached at a subdomain of a domain the company already uses for another
production system, which is what makes the DNS move of B11 a change to something already live and
not a greenfield step. Delivery is backlog B11.

**OQ-3. Message wording.** The Portuguese text of the daily list. Open because it is the
owner's voice, not a technical choice. Its shape stopped being open on 2026-09-02, when the owner
decided the message is a list whose line carries the client, the service and the days remaining
(section 4); what is still open is the exact wording of that line and of whatever heads the list.
Closed by the owner writing or approving both. Blocks nothing structural; a placeholder satisfies
every test. Since the two phase decision of 2026-08-31 it does not gate going live either, because
phase one sends no message at all; it gates phase two, beside OQ-1.

## 12. Development method

The method, test-first in two windows, decisions kept pure and effects behind narrow interfaces,
the clock injected everywhere, lives in `specs/testing.md` and binds every implementation window.

**Decision.** Four conventions the toolkit already enforced are canon, ratified by the owner on
2026-08-28: the user interface is in Portuguese, and code, tests, commit messages and every document
under `specs/` and `.claude/` are in English; framework-owned files (apps, migrations) are generated
by the framework's CLI and then edited, never hand-written; a code comment exists only where correct
code looks wrong, and it cites a canon identifier instead of restating its reasoning; prose in any
document carries no em dash, en dash or double hyphen.

*What this buys:* one voice per audience, and the standing rules of `CLAUDE.md` and the hooks now
resolve upward to this section instead of standing as orphans. *What this costs:* nothing beyond the
discipline the toolkit was already applying.

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

2026-08-28, revision after the review window. Section 12 ratifies four toolkit conventions (UI in
Portuguese and English elsewhere, CLI-generated framework files, the comment rule, the prose rule)
that a docs audit found only in `CLAUDE.md`; the owner had proposed them and promoted them.

2026-08-28, revision during B4. Section 6 keeps Django's administration site, with the framework's
standard authentication, mounted inside the secret path segment, by owner decision. Section 10's
non-goal on accounts now reads as the employee-facing application only. The health endpoint is still
the single route outside the segment.

2026-08-28, revision after B6, owner decision. Two changes taken together, both of which move the
frontier section 3 drew. First, the service stops being free text and becomes a choice from the
catalogue of section 3.1, seeded from the company's July 2026 declaration in section 3.2, with an
optional observation beside it; the record therefore carries its first foreign key to a reference
entity, which the original section 3 forbade, while the client stays a bare string exactly as
decided. Second, the form asks who is entering the record, and one person is one row however their
name is spelled, which adds I8 and widens I6 by one field. Section 10 narrows in the same pass:
what stays out is accounts, roles and authenticated attribution, and a self declared name is none
of those. What this buys: a queryable vocabulary and an audit trail that can count people. What
this costs: two reference tables to maintain, a catalogue the interface must be able to edit, and a
name that identifies without authenticating. Shapes in `specs/adr/0005-service-catalogue.md` and
`specs/adr/0006-submitter-identity.md`; delivery is backlog B12 and B13.

2026-08-31, revision, owner decision, foundation v0.2. Section 6's path segment stops being a
credential and becomes a short shareable link, with nothing put in its place: the application is
reachable by anyone holding or guessing the segment. The owner took that decision after being shown
Cloudflare Access and an application login as the two alternatives that keep a short address. The
configuration floor drops from sixteen characters to three, recorded in
`specs/adr/0001-configuration-boundary.md`, and the shape note lands in
`specs/adr/0003-secret-path-and-log-redaction.md`. I7 stays as written. What this buys: the short
address management asked for. What this costs: the application has no access control at all.
Delivery is backlog B18.

2026-08-31, revision, owner decision, foundation v0.3. Section 3 stops asking the employee for a due
date and asks for the date the service starts and a term in days, with the due date derived from the
two and still stored; the new section 3.3 carries the decision, and sections 1 and 3 are reworded in
the same pass wherever they said the form asks for a due date. Rows written before the term existed
are backfilled with the start date set to their due date and a term of zero, so no due date moves
and therefore no alert changes state (I1, I3). What this buys: the record holds the two facts the
business actually has, instead of the one number an employee computed from them in their head. What
this costs: a derived column that every write path has to keep true, and a stored term that is wrong
for the backfilled rows until a human corrects it. Shape in
`specs/adr/0007-service-term-and-derived-due-date.md`; delivery is backlog B19.

2026-08-31, decision, owner. OQ-2 closes. The host is a VPS the company already runs, shared with
its institutional site and with Ecobalance, and Cloudflare fronts it by Tunnel rather than by
proxied DNS, so the machine opens no inbound port and I6's trust in the forwarding headers is
structural instead of a firewall rule somebody maintains. The zone migration itself is deferred to
the pass that carries Ecobalance 2.0, because every project on that domain moves at once and the
two systems that cannot go down gain nothing from moving it now for an internal tool. Until then
the host's own nginx terminates TLS in front of this application, which costs the audit trail its
IP and country fields, since those come from Cloudflare headers that do not exist yet; the
submitter of section 6 still answers who entered a record. Delivery is backlog B11.

2026-08-31, decision, owner. Version 1 ships in two phases, recorded in the scope policy of section
0. Phase one is registration, audit and export, with no WhatsApp delivery at all and the alert
scheduler deliberately not deployed; phase two turns the engine on. What this buys: the registry
starts filling immediately, and a notification system with nothing to notify about is not shipped
as if it worked. What this costs: the engine sits written and unexercised against real data, and
the catch-up rule of I3 means the first successful run after phase two owes every warning whose
trigger date has passed, so phase two has to decide between accepting that burst and recording the
older warnings as handled without sending them. That consequence is written down now rather than
discovered on the day.

2026-08-31, revision, owner decision, in the same v0.3 pass. The company withdrew the five services
under `Sustentabilidade e ESG`, so the category is deactivated and section 3.2 carries a dated note
saying so. Rule 3 of section 3.1 governs: a withdrawn service is deactivated and never deleted, both
catalogue foreign keys are `PROTECT`, and a tracked record already points at one of the five. The
table of section 3.2 keeps all fifteen rows because it is the July 2026 declaration and not a
production table. What this buys: the registration form stops offering work the company does not do.
What this costs: nothing the existing records notice, since a deactivated category hides its
services from the form and hides nothing else. Delivery is backlog B20.

2026-09-02, revision, owner decision, foundation v0.4, section 4. The alert destination is a
WhatsApp group and not one person's chat, held in one configuration variable that accepts a group
identifier or a plain number. What this buys: everyone who acts on a deadline reads it at the same
moment. What this costs: every member of the group sees every client name, an internal disclosure
the owner accepts, and the group identifier is read from the vendor rather than typed, so
recreating the group is a configuration change. I4's list and OQ-1's exit criterion follow the new
wording. Delivery is backlog B26.

2026-09-02, revision, owner decision, in the same v0.4 pass, sections 4 and 5 and I1. One run sends
one message: the day's owed warnings are rendered as one list, one line per service carrying the
client, the service and the days remaining, and a run that owes nothing sends nothing. I1 now reads
one warning, one delivery, because a message carries many warnings and the guarantee was always
about the warning. What this buys: a person reads the whole day in one message, and the burst the
two phase decision predicted becomes one long message instead of fifty short ones, which is the
cheapest answer that question has had. What this costs: a rejected send fails every warning it
carried, which I2 already retries, and the first message after a backlog is long. OQ-3 keeps only
the wording. Delivery is backlog B27.

2026-09-02, decision, owner, code shape. The Evolution adapter speaks HTTP through the standard
library and adds no dependency. What this buys: one POST a day against a pinned local service does
not justify a package, its pin, its research and its supply chain, and the project's runtime stays
at three packages. What this costs: no connection pooling and no retry helper, neither of which
this product wants, and the adapter carries its own timeout and its own error mapping by hand.
Recorded here because it is the kind of choice a later session would otherwise reopen from habit;
its shape belongs to the ADR that lands with backlog B8.
