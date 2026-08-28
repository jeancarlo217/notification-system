# 0006. Submitter identity by normalized name

Status: accepted, 2026-08-28. Derives from `specs/foundation.md` section 6 and loses to it. It
records code shape only, for the delivery of backlog B13.

## Context

Foundation section 6 adds a fourth thing the registration form asks for: who is entering the
record. The owner's constraint has two halves that pull against each other. The field must be
free, because a name nobody anticipated has to be enterable as plain text and be saved as typed.
The field must also not breed duplicates, because `José Victor`, `jose victor` and `JOSÉ  VICTOR`
are one employee and the log has to say so.

I8 is the invariant that falls out of that pair. This document decides how it is enforced, and the
only interesting question is where the identity lives: in the string, or in a row the string
resolves to.

## Decision

**Identity is a row, and the typed string only resolves to it.** A `Submitter` model carries
`display_name` (the spelling first seen), `normalized_name` (unique, the identity key),
`is_active` (default true) and `created_at`. `Service` gains a required `submitter` foreign key
with `PROTECT`, for the same reason ADR 0005 gives: a submitter who leaves the company is
deactivated, never deleted, because records point at them.

Enforcing uniqueness on the raw string instead would be the obvious cheap move and it is wrong: it
makes `José Victor` and `jose victor` two people, which is precisely the defect the owner named.

**Normalization is a pure function**, `normalize_person_name` in a new `core/identity.py`, and it
does three things in this order: decompose with `unicodedata.normalize("NFKD", raw)` and drop the
combining marks, so accents stop mattering; `casefold`, so capitals stop mattering; split and
rejoin on whitespace, so runs of spaces and stray tabs stop mattering. `José  VICTOR ` becomes
`jose victor`.

It is a pure function on purpose. It is the whole of I8's logic, it needs no database and no Django
machinery to test, and `specs/testing.md` asks that a decision be reachable with plain data in and
plain data out. The bulk of B13's tests are calls to this function.

**What normalization deliberately does not do.** It does not strip punctuation, so `José Victor.`
is a second person. It does not reconcile nicknames, initials or surnames, so `José V.` is a third.
The rule is mechanical and predictable, and a wider one would eventually merge two real people who
share a first name, which is a worse failure than an occasional stray row an administrator can
merge by hand. The boundary is stated here so that nobody widens it in a later window believing it
was an oversight.

**Resolution is get or create on the normalized key**, with `defaults={"display_name": raw.strip()}`.
The database constraint is the enforcement, not the lookup: two concurrent creates raise
`IntegrityError` and the caller re-reads. SQLite and two typists make that race theoretical, and
the constraint is still what makes I8 true by construction rather than by timing, which is the same
reasoning I1 uses on the alert table.

**The first spelling wins.** A later submission typed `JOSE VICTOR` resolves to the existing row and
does not rewrite its `display_name`. The alternative, last spelling wins, would let one careless
entry rename the person everywhere in the interface and in every future export. An administrator
corrects a bad display name through the administration site, which registers `Submitter` alongside
the catalogue models of ADR 0005.

**Two people who genuinely share a name are one row.** That is a real cost of a self declared name
and the owner accepts it; the remedy is that the second one types a distinguishing name, which the
creatable field allows by construction.

**The form field is the creatable combobox** delivered by B14: a required field over the active
submitters, ordered by display name, that posts whatever the employee typed. The form's `clean`
normalizes it, rejects a value that normalizes to empty, and resolves it to the `Submitter`
instance. The two seeded names, `José Victor` and `Geovanna`, arrive in a data migration for the
reason ADR 0005 gives about the catalogue: they are data, not code, and the list grows through the
interface.

**Attribution is per record, not per edit.** The submitter is who registered the service. Editing a
due date and marking a service completed ask nobody for a name, because asking would add friction
to a two click action and because per action attribution is editing history, which foundation
section 10 still defers. The audit entry for an edit carries the record's submitter, which says who
owns the record, not who touched it that afternoon. This is a real limit and it is written down so
that a later reader does not mistake it for a bug.

**The audit entry gains one field.** `log_service_submission` takes the submitter id and writes it
as `submitter_id` next to `service_id`, on the path ADR 0004 already built. The IP and the
Cloudflare country stay exactly as they are: the name is a claim by an anonymous visitor, the
address is what the network observed, and losing the second because the first arrived would be a
downgrade of I6.

## Consequences

The interface can now answer "who entered this" with a name instead of an address, which is what
the owner asked for, and the log can group a person's submissions by a stable identifier rather
than by string equality.

Nothing here authenticates anybody. Anyone holding the secret link can type any name, including
somebody else's. The name is useful, not evidential, and foundation section 10 is revised in the
same pass to say so, so that no later window reads `Submitter` as the beginning of user accounts.

B10's CSV export gains a submitter column carrying the display name.

Every existing test that creates a `Service` needs a submitter, the same churn ADR 0005 causes for
the catalogue, and for the same reason.
