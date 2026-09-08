# 0001. The configuration boundary

Status: accepted, 2026-08-28. Derives from `specs/foundation.md` and loses to it. It records code
shape only, for the delivery of backlog B2.

## Context

I4 puts the thresholds, the destination number, the message template and the secret path in
versioned configuration and forbids them as literals in code. I5 forbids a real credential in the
repository. Foundation section 8 says configuration comes from the environment, and section 5
computes today in a named time zone. Nothing above this document says where that reading happens,
in what shape the values arrive, or what a bad value does.

Three tracks depend on the answer. The screens and safety track (B4, B5, B6, B10) needs the secret
path segment and the time zone, the engine track (B7, B9, B8) needs the thresholds, the number and
the template, and deployment (B11) needs the list of variable names to provision on the host.

## Decision

**One function, called once.** `deadliner/config.py` holds `load_config(env)`, a pure function from
a mapping to frozen dataclasses (`DjangoConfig`, `DeadlinerConfig`, `Config`). The settings module
calls it once with `os.environ` and exposes the business half as `settings.DEADLINER`. No other
module reads the environment. Application code goes through the typed accessor `get_config()`,
because an attribute of Django's lazy settings object is `Any` under `mypy --strict`.

Purity is the point. The rules below are testable with literal dictionaries, with no environment
patching and no Django machinery, which is what `specs/testing.md` asks of a decision.

**Variable names.** `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS` and
`DJANGO_DATABASE_PATH` for infrastructure, unchanged from B1. `DEADLINER_ALERT_THRESHOLDS`,
`DEADLINER_WHATSAPP_NUMBER`, `DEADLINER_MESSAGE_TEMPLATE`, `DEADLINER_SECRET_PATH_SEGMENT` and
`DEADLINER_TIMEZONE` for the business values.

**No business value has a default in code.** All five are required and a missing one is an error.
A default of `(30, 7, 0)` compiled into the module is the literal I4 forbids, however overridable
it is. The tracked `.env.example` is the versioned configuration that carries them, and a test
asserts that file loads without error.

**Every problem is reported at once.** `load_config` collects the failures and raises one
`ConfigError`, a subclass of Django's `ImproperlyConfigured`, naming every offending variable.

**An error names its variable, and for the secret path segment alone it never repeats the value**,
because that text reaches the logs (I7).

**Canonical forms, which no later item re-decides.**

| Value | Form | Reason |
| --- | --- | --- |
| Thresholds | `tuple[int, ...]`, distinct, ordered from the earliest warning to the due date | the loader owns the order, so no caller sorts again |
| Number | digits only, country code first, no plus sign | every vendor format is reached by adding characters to this one, and OQ-1 is still open on the exact form Evolution API accepts |
| Template | a `str.format` string over `MESSAGE_TEMPLATE_FIELDS` | those four fields are the ones foundation section 4 names |
| Path segment | at least 3 characters of `A-Za-z0-9_-` | foundation section 6, revised on 2026-08-31, wants a short link people can be sent and can type; the floor only keeps the URL mount from being handed an empty or one letter value |
| Time zone | a `zoneinfo.ZoneInfo`, resolved at startup | an invalid name is caught on boot rather than during a run |

**Two B1 behaviours tightened.** `DJANGO_DEBUG` accepts `0` or `1` and errors on anything else,
where B1 read every other value as off. An empty `DJANGO_ALLOWED_HOSTS` with debug off is an error,
because that pair refuses every request.

## Consequences

B7 renders warnings against `MESSAGE_TEMPLATE_FIELDS` imported from this module rather than
retyping the names. B8's adapter maps the digits-only number into the `number` field of Evolution's
send body, whose shape the spike recorded in `specs/dependencies.md` while OQ-1 stays open. B11
provisions the nine variables of this project on the host, alongside the Evolution keys that the
spike added and that this boundary does not read.

A missing or malformed variable stops the process at startup instead of failing later. That is the
intended trade: the daily run must not discover a broken template at send time.

The message template needs quoting in a dotenv file because it contains spaces. Both `just` and
Docker Compose strip the surrounding quotes, verified on 2026-08-28 and recorded in
`specs/dependencies.md`.

Test fixtures for the secret path segment use obviously fake low entropy values, because the
gitleaks rule `generic-api-key` fires on an alphanumeric string of sixteen or more characters near
the word secret. Allowlisting the test directory would blind the C5 gate exactly where a real
credential could one day be pasted, so the fixture gives way instead. B5 will meet the same rule.

Changed 2026-08-31 by the owner decision of foundation section 6 v0.2. The segment is no longer a
credential, so its floor drops from sixteen characters to three and the reason column above no
longer argues from unguessability. Two things did not change and are worth stating, because both
look wrong now: the error message still omits the offending value, and the segment is still
redacted before any line is written (I7). Both are cheap, both are what an invariant asks for while
it stands, and neither is evidence that the segment is still secret.

Changed 2026-09-02 by the two owner decisions of foundation section 4, v0.4. Three things move in
this boundary, and the delivery is backlog B26 and B27.

The `Number` row above becomes a destination row. `DEADLINER_WHATSAPP_NUMBER` becomes
`DEADLINER_WHATSAPP_DESTINATION` and its canonical form is either the digits-only number it already
accepted or a group identifier, the vendor's `<digits>@g.us`, kept verbatim. The reason column's
hedge about OQ-1 is answered for this field: the Evolution source at tag `2.3.7` returns any string
already carrying `@g.us` untouched from `createJid`, and the send body's `number` field is an
unconstrained string, so one field carries both forms and the loader validates rather than
transforms. One variable and not two, because two would need a rule about which destination wins
and foundation section 10 keeps the product at one destination.

`MESSAGE_TEMPLATE_FIELDS` keeps its four names, and `DEADLINER_MESSAGE_TEMPLATE` keeps its meaning
narrowed to one line of the list. Beside it `DEADLINER_MESSAGE_HEADER` carries what heads the list,
validated the same way over its own field set, which is the count of warnings and the date. The
count is a field and not a sentence in code for the same reason every other business string is
configuration (I4).

The Evolution adapter's own values, the base URL, the API key and the instance name, enter through
this boundary too rather than through a second reader, because ADR 0001 says nothing else in the
project reads `os.environ`. They are infrastructure and not business values, so they sit beside
`DJANGO_DATABASE_PATH` in `DjangoConfig` rather than in `DeadlinerConfig`, and the API key is a
credential: it never appears in a `ConfigError` message, the same rule the secret path segment
already carries and for the same reason (I5, I7).
