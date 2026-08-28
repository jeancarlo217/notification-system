# 0002. The scheduler container

Status: accepted, 2026-08-28. Derives from `specs/foundation.md` and loses to it. It records code
shape only, for the delivery of backlog B9.

## Context

Foundation section 5 decides the engine is a Django management command executed once a day by a
scheduler that lives in the Compose stack, outside the web process, with no Celery, no Redis and
no queue. It does not say what the scheduler process is. The invariants make the choice easy to
get right: I1 makes a duplicate run harmless (the uniqueness rule on the persisted alert absorbs
it), and I3 makes a missed or late run cost lateness at most, because the next run derives what is
owed from the records. The scheduler therefore needs no precision, no persistence and no memory;
it only has to invoke `send_alerts` about once a day, forever, and fail loudly when the command
fails.

## Decision

**A `scheduler` service in `compose.yaml`, built from the project's own image, running a shell
loop.** The loop invokes `python manage.py send_alerts`; on success it sleeps 24 hours, on failure
it retries after 1 hour. The service mounts the same `data` volume and `.env` file as `web` and
restarts `unless-stopped`.

Two consequences of the loop shape are accepted on purpose:

- The run time is the container's start time and drifts by the command's own duration. Daily
  granularity is all section 5 asks, and the catch-up rule makes the exact hour irrelevant.
- A restart runs the command immediately. That is a deliberate feature, not a bug: after downtime
  the catch-up rule sends what is owed, and I1 makes the extra run at worst a no-op.

The hourly retry exists for the failure path: a run that dies (the database not yet migrated on
first boot, the provider factory refusing while B8 is undelivered, a broken configuration) is
retried within the hour rather than silently costing a full day. The failure itself stays loud in
the container log.

Rejected alternatives: cron inside the container (a package to install, and cron strips the
environment, which is exactly where this project keeps its configuration); a dedicated scheduler
image such as Ofelia or supercronic (a new dependency and a second place to configure, bought for
precision the invariants make worthless); host cron outside Compose (breaks the one-stack decision
of foundation section 8 and reopens OQ-2 territory).

## Consequences

The scheduler is the first consumer of `send_alerts` in production shape. Until B8 delivers the
Evolution adapter, every run fails loudly on the provider factory naming OQ-1, and the loop
retries hourly; the service becomes quiet and useful the moment the adapter lands, with no change
here. B11 inherits nothing to provision for it beyond the same `.env` the stack already reads.

The end to end idempotency proof named by backlog B9 lives in `tests/test_scheduler.py`: the
command fired twice for the same day delivers each owed warning once. The loop itself carries no
logic worth a test; what it invokes is what the test invokes.
