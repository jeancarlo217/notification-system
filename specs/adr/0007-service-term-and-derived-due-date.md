# 0007. The service term and the derived due date

Status: accepted, 2026-08-31. Derives from `specs/foundation.md` section 3.3 and loses to it. It
records code shape only, for the delivery of backlog B19.

## Context

Foundation section 3.3 stops the registration form asking for a due date and has it ask for the date
the service starts and a term in days. Nothing above this document says what the two fields are
called, whether the due date survives as a column or becomes a computed attribute, where the
arithmetic lives, or what happens to the rows written before the term existed.

The due date is not an ordinary attribute here, which is what makes the shape worth a decision. Four
things already reach for it in the database rather than in Python: the daily run selects the
services whose trigger date has arrived, the uniqueness rule behind I1 hangs off the alert rows that
run writes, the list orders by it, and B17's paging walks that ordering. Whatever shape the
derivation takes has to leave all four of them deciding in SQL.

## Decision

**`Service` gains `start_date` and `term_days`, and `due_date` stays a stored column.** The two new
fields are the input the employee gives. `term_days` is a whole number of days and zero is a valid
value, because the backfill below writes it. The column is the output that everything downstream
already reads.

**`due_date` is deliberately not a Python property.** A property is not a database expression. The
moment the due date stops being a column, the run's filter, the list ordering and B17's search have
to load rows and decide in Python, which is one query per row against the constant-query rule of
foundation section 8, and the uniqueness rule behind I1 loses the persisted field its alert rows
hang off. A stored column buys all four back for the price of one denormalization. This is the whole
reason the column survives the decision, and it is written here so that nobody deletes it in a later
window believing it is redundant with the two fields beside it.

**The arithmetic is a pure function.** `due_date_from(start_date, term_days)` lives in a new
`core/terms.py` that imports nothing from Django, exactly as `normalize_person_name` lives in
`core/identity.py`. Plain data in, plain data out, so the rule is reachable without a database and
carries the bulk of B19's tests, which is the shape `specs/testing.md` asks a decision to take.

**`Service.save` derives the column on every write.** This is the precedent ADR 0006 set for
`Submitter.normalized_name`, adopted for the same reason: the rule is a property of the table, so it
cannot depend on which door the row came through. The form, the administration site, a data
migration and a future import all reach the same due date without knowing the arithmetic. A caller
that assigns `due_date` by hand has it replaced on save rather than honoured, which is the only
answer that keeps a derived column and its inputs from disagreeing.

**The administration site shows `due_date` read only.** It is the one door where a human can type
into a derived column, and offering a field whose value the next save silently overwrites is worse
than not offering it.

**The lifecycle edit that moves a deadline edits the inputs.** A screen that writes `due_date` would
have its value replaced by the following `save`, so moving a deadline means editing the start date
or the term and letting the due date follow. What that route and that form are called is B19's to
settle, and every caller reverses the route name rather than writing a path, as it already does.

**Existing rows are backfilled with `start_date = due_date` and `term_days = 0`**, in a data step
between adding the two columns as nullable and making them required. Every due date comes out of
that backfill identical to the one that went in, so no service moves between thresholds, no alert
changes state, and no warning fires twice or goes missing (I1, I3). The term it writes is a
placeholder and it is wrong for every row that had a real term. Nothing in the system can recover
that term, and inventing a plausible one would be a guess wearing the clothes of a fact, so the
backfill says zero and a human corrects the row.

**Field names are `start_date` and `term_days`; the Portuguese labels are interface text and are
not settled.** The labels shipping are `Data de início` and `Prazo (dias)`. This is the same
distinction the project recorded on 2026-08-28 for the B12 and B13 fields: changing a label is one
line and changing a field name is not.

## Consequences

`core/engine.py` is untouched. It filters and renders against `due_date` exactly as it did, and
`MESSAGE_TEMPLATE_FIELDS` in ADR 0001 keeps its four names, so no configured template breaks. The
list ordering and B17's search are untouched for the same reason, which is the point of keeping the
column.

B10's exported row carries the start date and the term beside the due date. The due date stays in
the row because it is what the warnings measure against and what a person sorting the spreadsheet
reaches for first.

Every test that constructs a `Service` with `due_date=` constructs one with a start date and a term
instead. That churn is the third of its kind here, after ADR 0005 and ADR 0006, and it is
unavoidable for the same reason: the model changed.

Unlike step 4 of ADR 0005 and the unattributed rows of ADR 0006, this migration deletes nothing and
rests on no precondition about B11 not having shipped. It would be correct against a production
database, which is the first migration in this project of which that can be said.
