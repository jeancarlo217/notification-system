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
| Number | digits only, country code first, no plus sign | every vendor format is reached by adding characters to this one, and OQ-1 has not said what Evolution API wants |
| Template | a `str.format` string over `MESSAGE_TEMPLATE_FIELDS` | those four fields are the ones foundation section 4 names |
| Secret segment | at least 16 characters of `A-Za-z0-9_-` | foundation section 6 calls the link a credential, and a short segment is not one |
| Time zone | a `zoneinfo.ZoneInfo`, resolved at startup | an invalid name is caught on boot rather than during a run |

**Two B1 behaviours tightened.** `DJANGO_DEBUG` accepts `0` or `1` and errors on anything else,
where B1 read every other value as off. An empty `DJANGO_ALLOWED_HOSTS` with debug off is an error,
because that pair refuses every request.

## Consequences

B7 renders warnings against `MESSAGE_TEMPLATE_FIELDS` imported from this module rather than
retyping the names, and B8's adapter maps the digits-only number into whatever shape the spike
settles on. B11 provisions the nine variables above on the host.

A missing or malformed variable stops the process at startup instead of failing later. That is the
intended trade: the daily run must not discover a broken template at send time.

The message template needs quoting in a dotenv file because it contains spaces. Both `just` and
Docker Compose strip the surrounding quotes, verified on 2026-08-28 and recorded in
`specs/dependencies.md`.

Test fixtures for the secret path segment use obviously fake low entropy values, because the
gitleaks rule `generic-api-key` fires on an alphanumeric string of sixteen or more characters near
the word secret. Allowlisting the test directory would blind the C5 gate exactly where a real
credential could one day be pasted, so the fixture gives way instead. B5 will meet the same rule.
