---
name: systematic-debugging
description: Four-phase debugging methodology with root cause analysis for this project (Django templates, SQLite, a daily alert engine, Evolution API for WhatsApp). Use when investigating bugs, fixing test failures, or troubleshooting unexpected behavior. Emphasizes NO FIXES WITHOUT ROOT CAUSE FIRST.
---

# Systematic debugging

## Core principle

**NO FIXES WITHOUT ROOT CAUSE FIRST.**

Never apply a patch that masks the underlying problem. In this product the stakes are concrete: a lost
warning is an expired license with a client's name on it, and a duplicated warning teaches the company
phone to ignore the system.

## Four-phase framework

### Phase 1: reproduce and investigate

1. **Write a failing test** that captures the wrong behaviour. It is the regression test afterwards.
2. **Read the error message in full**, every frame.
3. **Look at what changed** (`git diff`, `git log`), and what the behaviour was supposed to be: the
   invariant or foundation section that specifies it.
4. **Trace the data flow** to where the bad value is born, not where it surfaces.

### Phase 2: isolate

Narrow it down. Log at the decision points, not everywhere, and never log the secret path segment (I7) or
a message body.

### Phase 3: state the root cause as a violated assumption

Not "the alert did not send" but "the engine assumed the alert record existed before the send, and this
path attempts the send first, so a crash between the two loses the attribution". A root cause stated as
an assumption tells you whether the fix is local or whether the same assumption lives in four places.

### Phase 4: fix and prove

The fix addresses the cause, the reproduction test passes and would have failed before, and
`/quality-gate` is green.

## The failure modes this system actually has

**Duplicate sends (I1).** Two messages for one warning is almost always the uniqueness rule missing or
checked in Python instead of enforced by the database, or the scheduler and a manual run racing. The
canonical probe: run the engine twice against the same records and count deliveries on the provider fake.

**Silent loss (I2).** A warning that never arrived and nothing shows it: an exception swallowed around
the provider call, an alert state no view lists, or the daily query filtering out the failed state so the
retry never happens. If a human cannot see it in the interface, it is lost even when a log line exists.

**Time and timezone (I3).** "Today" computed in UTC instead of America/Campo_Grande fires alerts a day
early or late around midnight. A naive datetime compared to an aware one. A decision function calling the
real clock, which makes the bug unreproducible in a test. The catch-up rule not firing after missed days
means owed-ness is being derived from something other than the persisted records.

**Config that is secretly code (I4).** A behaviour that does not change when the configuration changes
means a literal is shadowing the setting somewhere.

**Attribution and the proxy (I6).** Audit entries all showing the same IP means the code is reading
`REMOTE_ADDR` (which is Cloudflare's edge) instead of the forwarding header; a spoofed-looking country
means the header is being trusted on traffic that did not come through Cloudflare (OQ-2's deployment
contract).

**The secret in the logs (I7).** Any new logger, error handler or third-party middleware is a new path
the redaction must cover. The probe is the invariant's own test: request a secret-path route, capture
logs, grep for the segment.

**SQLite under concurrency.** `database is locked` when the web process and the daily engine write at
once: keep transactions short, and remember the engine writes the alert record before and after the send
on purpose (section 2 of the foundation), so hold no transaction open across the network call.

**The Evolution adapter.** Timeouts, a disconnected instance, an accepted-but-not-delivered response.
The interface records the outcome it was given; whether Evolution accepted is what I2 tracks, and a
deeper delivery guarantee is not promised by the foundation. A bug that only reproduces against the real
instance belongs in the few integration tests, behind OQ-1's spike.

## Tooling

```bash
just test --pdb -x           # drop into the debugger on the first failure
just test -k "<name>" -vv
```

For the daily engine, run the management command directly with the injected clock pinned in a test
rather than waiting for the scheduler. Query-count assertions
(`django.test.utils.CaptureQueriesContext`) catch a per-row query in the export or the engine before it
ships.

## Checklist before claiming it is fixed

- Root cause identified and stated as the violated assumption.
- The reproduction test passes and would have failed before.
- The gate is green.
- Nothing was silenced: no bare `except`, no suppressed lint, no test weakened to make it pass.
- If the bug violated an invariant, the test names it (I1 to I7).
- If the root cause was a wrong assumption written down somewhere, the document is fixed too.

## Red flags

Stop if you are thinking "quick fix now, investigate later", "one more attempt" after three failures, or
"this should work" without knowing why. Three consecutive failed fixes means the problem is
architectural: stop and discuss.
