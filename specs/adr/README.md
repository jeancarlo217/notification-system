# ADR conventions

ADRs record code shape only; the what and the why stay in `specs/foundation.md`, which every ADR
derives from and loses to.

One file per decision area: `NNNN-kebab-title.md`, numbered from `0001`, with the sections
Context, Decision and Consequences. An ADR is edited in place when its decision evolves, with a
dated note on every change, so the set always reads as the current truth rather than a history.
Cite canon identifiers (I3, OQ-1) instead of copying their reasoning; a copy is outside the
fan-out and drifts. A new ADR, or a change to one, gets a line in `specs/log.md` in the same
pass.

No ADR exists yet. Likely first candidates, to be written only when the work forces them: the
notification provider interface and its Evolution adapter (after the OQ-1 spike), the secret-path
middleware and log redaction shape, and the scheduler container.
