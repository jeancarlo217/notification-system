# ADR conventions

ADRs record code shape only; the what and the why stay in `specs/foundation.md`, which every ADR
derives from and loses to.

One file per decision area: `NNNN-kebab-title.md`, numbered from `0001`, with the sections
Context, Decision and Consequences. An ADR is edited in place when its decision evolves, with a
dated note on every change, so the set always reads as the current truth rather than a history.
Cite canon identifiers (I3, OQ-1) instead of copying their reasoning; a copy is outside the
fan-out and drifts. A new ADR, or a change to one, gets a line in `specs/log.md` in the same
pass.

`0001-configuration-boundary.md` records the shape B2 delivered, `0002-scheduler-container.md` the
shape B9 delivered, `0003-secret-path-and-log-redaction.md` the shape B5 delivered, and
`0004-audit-and-structured-logging.md` the shape B6 delivered. Likely next candidate, to be written
only when the work forces it: the notification provider interface and its Evolution adapter, after
the OQ-1 spike.
