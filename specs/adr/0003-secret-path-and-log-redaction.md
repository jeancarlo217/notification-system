# 0003. The secret path prefix and log redaction

Status: accepted, 2026-08-28. Derives from `specs/foundation.md` and loses to it. It records code
shape only, for the delivery of backlog B5.

## Context

Foundation section 6 decides there is no login: the whole application is served under a secret
path segment held in configuration, the health endpoint used by the container runtime is the
single route outside it, and Django's administration site sits inside the segment keeping the
framework's standard authentication. I7 adds the property that makes the link survive its own
operation: the segment is redacted on the logging path before any line is written, because request
paths reach the logs by default and access logs are the most copied artifact a web application
produces.

The segment is a credential, so the two questions are where the prefix is applied and where the
redaction sits. Both have a cheap answer and an expensive one, and the cheap one is correct here.

## Decision

**The prefix is applied in the root URL configuration**, which reads the segment from
`get_config()` (I4) and mounts three entries: `health/` first and outside the segment,
`<segment>/admin/` for the administration site, and `<segment>/` including `core.urls`. Nothing
else changes: `reverse()` and `{% url %}` produce the prefixed path for free, so no template, view
or test names a path by hand.

Rejected alternative: middleware stripping the prefix from `PATH_INFO`, or `FORCE_SCRIPT_NAME`.
Both add a moving part to solve what the URL configuration already solves, and both leave
`reverse()` needing help.

**The redaction is a `logging.Filter` installed on the handlers**, not on a logger.
`SecretPathRedactionFilter` in `deadliner/log_redaction.py` replaces the segment with the
placeholder `[secret-path]` in the interpolated message and clears the record arguments. It is
attached to the single `console` handler in `LOGGING`, and the `django` logger is redefined to use
that same handler.

A filter on a logger only sees records created by that exact logger, never records propagated from
a child, so logger-level redaction would cover whichever loggers someone remembered to list. On the
handler it sees every record that any logger in the process writes, which is the property I7 asks
for. Redefining the `django` logger is not decoration: Django applies its own `DEFAULT_LOGGING`
with `dictConfig` first and the project's `LOGGING` second, so a `django` logger left alone keeps
handlers this project does not own and does not filter.

The health view is `core.views.health`, returning a plain `ok` and touching no dependency, and
`compose.yaml` points the web service healthcheck at it.

## Consequences

The secret segment is now part of the URL configuration built at import time, so changing it needs
a process restart rather than a request. That matches how it is rotated: an environment change and
a redeploy.

Redaction covers the message of every record. It does not rewrite a formatted traceback, so a
future view that puts a request path into an exception argument could still print it inside a
stack trace; no code does that today, and the honest guard for it is not adding one.

Gunicorn is outside Django's logging configuration entirely. Its access log is disabled by default
in the pinned 26.2.0, which is why nothing leaks today, and turning it on with `--access-logfile`
would write the full path past this filter. That trap belongs to B11 and is recorded in
`specs/dependencies.md`.

The interface is not structured yet and carries no correlation keys. That is backlog B6, which
owns the same `LOGGING` block by the conflict rule of the parallel plan and will extend it in
place.

Changed 2026-08-28 by B6: the filter no longer looks only at the message. It checks every value
the record carries, in the form the formatter will write it, because structured logging renders
anything that is not a string through `str()` and Django's own `django.request` records carry the
request object with the full path on it. The `plain` formatter named above is now the JSON
formatter of `0004-audit-and-structured-logging.md`, and the console handler carries a second
filter that binds the correlation keys.
