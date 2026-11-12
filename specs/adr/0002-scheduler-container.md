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

**Note, 2026-11-09, the run has an hour.** Foundation section 5 v0.6 makes the list owed once a day
from a configured send time, 07:00 in America/Campo_Grande, retried every hour after a failure, and
I1 becomes one day, one list. The two consequences this ADR accepted on purpose stop being true:
the run time is no longer the container's start time, and a restart no longer sends anything
before the send time. The loop above is superseded by the shape below, delivered by backlog B27.

**The loop polls and the command decides.** The `scheduler` service runs `send_alerts` every sixty
seconds and does nothing else; on a failure it logs and goes on polling. Whether a list is owed at
this instant is a pure function of the injected clock, the configured send time and zone, and the
dispatch record of today, if any: owed when the local time is at or past the send time and today
has no record, or has a failed one whose last attempt is at least an hour old. A run that owes
nothing exits zero without a provider call and without a log line above debug, because sixty runs
an hour that each announce they did nothing would bury the one that did something.

Rejected: a shell loop that sleeps until the next seven o'clock, because that arithmetic lives in
`sh` in the host's zone where no test reaches it and is exactly the clock read inside a decision
the method forbids; and cron or a scheduler image, for the reasons this ADR already gave. Polling
costs a Django start a minute, which at this scale is noise, and it buys a message within a minute
of the hour with all the timing in tested Python.

**One dispatch row per day replaces the alert row per service and threshold.** It carries the local
date, unique by construction (I1), its state (`pending`, `sent`, `failed`), the number of services
listed, the time of its last attempt and its timestamps. The row is written `pending` before the
provider is called and moved to `sent` or `failed` by the answer, so two concurrent runs collide on
the uniqueness rule rather than both sending. A row left `pending` by a run that died mid send is
treated as failed once its last attempt is an hour old, because a pending that never resolves is a
silent terminal state (I2). The one hour retry interval is a module constant on B17's precedent:
the owner decided it, and it is how often a machine tries again, not a value the business tunes.

The `Alert` model and its table are removed by a migration B27 generates. Phase two never ran in
production, so the production table is expected to be empty; B27 confirms that on the host before
the migration ships rather than assuming it.

**Delivered by B27 on 2026-11-12**, with three shapes worth stating. The command looks its
provider up only when a list is actually sent, because a poll that owes nothing must not fail on
a provider it never needed, which is every poll until B8. A retry claims the day's row with an
update conditional on the attempt time it read, so two runs retrying at once cannot both send
(I1). And a provider that raises instead of answering `False` leaves the row `failed` and the
error loud, never a row stuck `pending` (I2). The model is `Dispatch`, in migration `0018`.
