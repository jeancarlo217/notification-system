# The Canon axis, in detail

Reference for the **Canon** axis of `code-review`: a checklist of **what a violation looks like in
code**, not a restatement of the decisions. Each row cites the authority, and the authority
(`specs/foundation.md` section 9, unless noted) is where the reasoning lives.

**Every row here blocks.** An invariant is law with a pass or fail acceptance test, and the answer to a
failure is never to weaken the rule. If the rule is genuinely wrong, that is a foundation revision with a
logged entry, decided by the owner, not a compromise reached inside a review.

## The invariants, as they fail in a diff

| Invariant | What a violation looks like |
| --- | --- |
| **I1** one warning, one message | a send with no uniqueness rule on (service, threshold) persisted before the attempt; the engine deciding "already sent" from process memory, a flag on the service row, or anything a second concurrent run cannot see; a resend path that creates a fresh alert instead of reusing the record |
| **I2** nothing fails silently | a caught exception around the provider call that logs and moves on without persisting a failed state; an alert state machine with a state no view lists; a failed alert the next run's query does not pick up |
| **I3** the schedule survives death | owed-ness computed from anything but persisted records plus the injected date; `datetime.now()` or `timezone.now()` called inside a decision function; a naive datetime, or "today" computed in UTC instead of America/Campo_Grande; a scheduler that enqueues future sends at registration time |
| **I4** business values are data | a threshold (30, 7, 0), the alert destination, a message template or the secret path segment as a literal in a function or a migration; a config value read somewhere other than the settings boundary |
| **I5** no secret in the repository | a credential, an API key, a real `.env`, a SQLite database file, or production data in the diff; a default in code that is a real credential; a fixture copied from the live database |
| **I6** every write is attributed | a form POST handled with no audit log entry; the IP read from `REMOTE_ADDR` instead of the Cloudflare forwarding header; audit fields assembled in each view instead of once on a shared path |
| **I7** the link never leaks into its own logs | a log line, error message or exception that can carry the full request path unredacted; the secret segment interpolated into a user-visible URL that gets logged; redaction implemented in callers instead of on the logging path |

## Code shape

| Check | Authority |
| --- | --- |
| decisions are pure: schedule computation, threshold evaluation, message rendering and CSV shaping take plain data in and out, no clock, no network, no ORM | `specs/testing.md` |
| the notification provider is one narrow interface with a real Evolution adapter and a test fake; no code outside the adapter imports the vendor's client or speaks its HTTP shapes | foundation section 4 |
| the clock is an effect: anything depending on "now" receives it as a value or an injected clock | `specs/testing.md` |
| migrations generated with `makemigrations`, never hand-authored | `CLAUDE.md` |
| no per-row queries in the export or the daily run; a constant number of queries | foundation section 8 |
| no dependency chosen or asserted from memory; new ones walk `specs/dependencies.md` | `CLAUDE.md` |
| the health endpoint is the single route outside the secret path and touches no dependency | foundation section 6 |

## Language

Code, tests, comments, commits and documents are English. User-facing strings in templates are
Portuguese. A Portuguese identifier in code is a finding; a Portuguese sentence in a template is not.

## Data that may never enter the repository

No secret and no production data in any form, at any time (I5): no `.env` with real values, no SQLite
database file, no credential, no export of real client rows as a fixture. A test fixture is synthetic
with invented client names.
