# 0004. The audit trail and structured logging

Status: accepted, 2026-08-28. Derives from `specs/foundation.md` and loses to it. It records code
shape only, for the delivery of backlog B6. It extends the logging path that
`0003-secret-path-and-log-redaction.md` opened.

## Context

Foundation section 6 decides there is no login, so the audit entry is the only answer to who
entered a record: I6 asks every form submission for the submitter's address, the country
Cloudflare reports, the timestamp and the identifier of the record touched. The address and the
country are trustworthy only because all traffic arrives through Cloudflare, which is the
deployment contract of OQ-2. The observability rule of section 8 adds that logs are structured and
carry their correlation keys, bound once per request or run.

Three things had to be decided: what a line looks like, where the per request keys are bound, and
what counts as a submission.

## Decision

**One JSON object per line.** `JsonFormatter` in `deadliner/log_format.py` writes the timestamp in
the configured time zone, the level, the logger name, the message, and then every key the caller
passed as `extra` or the context bound. Nothing else is added, and no logging package was
introduced for it: the formatter is fifteen lines against the standard library.

**The correlation keys are bound by a middleware, first in the chain.**
`RequestContextMiddleware` in `deadliner/log_context.py` binds a fresh request identifier and the
submitter's origin into a `ContextVar`, and resets it when the request ends, so a line written
outside a request carries no origin. `LogContextFilter` copies whatever is bound onto every record
that reaches the handler. The daily command binds a run identifier the same way, which is what
makes a send line traceable to the run that wrote it.

**The address and the country come from `CF-Connecting-IP` and `CF-IPCountry`, and from nowhere
else.** A request that arrives without them logs both as null. Falling back to the socket address
would write Cloudflare's own address, or a lie, into the trail that exists to answer who submitted
something.

**A submission is an accepted write.** The three writing views call
`core.audit.log_service_submission` with the identifier of the record they touched, after the
write succeeds. A refused form and a page view are not submissions and produce no entry.

**The application writes its own request line.** Django logs a 4xx or 5xx response from
`BaseHandler.get_response`, which runs after the middleware chain has exited and the bound context
is already gone, so the framework's own `Not Found` line cannot carry a correlation key. The line
that carries one is the `request` event the middleware writes before it resets.

## Consequences

Redaction had to widen. A structured field carrying a request path leaks exactly what a message
would, and the formatter renders anything that is not a string through `str()`, which is how
Django's `django.request` records, that carry the request object itself, would have written the
secret segment. The filter of ADR 0003 now checks every value in the form it will be written in.
The B5 test that reads the real log stream is what caught it.

The trail says which record was touched, not what was done to it. Foundation section 6 asks for
the identifier and nothing more, so a creation and a completion look alike apart from their
timestamps. Adding the action is a one line change if the owner asks for it.

The country field depends on a Cloudflare setting, not only on Cloudflare being in front: the
`CF-IPCountry` header is added by the "Add visitor location headers" Managed Transform. Recorded in
`specs/dependencies.md` and part of what OQ-2 has to answer, because I6 is untestable in production
without it.
