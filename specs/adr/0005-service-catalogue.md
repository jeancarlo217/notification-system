# 0005. The service catalogue

Status: accepted, 2026-08-28. Derives from `specs/foundation.md` section 3.1 and loses to it. It
records code shape only, for the delivery of backlog B12.

## Context

Foundation section 3.1 turns the service from free text into a choice from a catalogue held in the
database, three categories and fifteen services as the company declares them in July 2026, and it
names four rules the catalogue obeys. Nothing above this document says what the tables are called,
how the fifteen rows arrive, what happens to the free text column the form has used until now, or
what the form reads to build its options.

The naming collision is the first thing to settle, because it decides every other name in the file.
This project already owns a model called `Service`, and here it means one tracked deadline. In the
sister project, Ecobalance, `Service` means one catalogue entry. Both cannot keep the name.

## Decision

**The catalogue is `ServiceCategory` and `CatalogService`, and the tracked deadline keeps the name
`Service`.** Renaming the existing model would touch every application module, both migrations and
roughly a hundred and fifty tests, to buy vocabulary alignment with a system this one does not talk
to yet. `CatalogService` is the local name for what Ecobalance calls `Service`, and its docstring
says exactly that, so the correspondence is written down once instead of being folklore. If the two
systems ever share a schema, that rename is a mechanical pass done with a reason.

**Fields.**

`ServiceCategory`: `name` (unique), `position` (small integer that orders the menu), `is_active`
(boolean, default true). **A category being inactive hides every service under it from the
registration form**, and it hides nothing else: records already pointing at a service in that
category keep displaying, keep being editable and keep earning warnings, exactly as they do when
the service itself is deactivated. So a service is offered when it is active and its category is
active, which is one condition on one query rather than a second concept. There is deliberately no
`parent`. Ecobalance carries a nullable self
reference that is null in every row today, and REQ-148 forbids subcategory as an entity, so the
column here would buy nothing and invite someone to fill it.

`CatalogService`: `category` (foreign key), `name`, `position`, `is_active`,
`ecobalance_service_id` (nullable positive integer, unique when set). Unique together on
`(category, name)`, which is rule 3 of section 3.1 expressed as a constraint rather than as a
convention. There is no `reference_value_brl` and no `property_requirement`: both belong to
Ecobalance's contracts, this system tracks deadlines, and a column nothing reads is a column that
will eventually lie.

`Service`, the existing model: `description` is renamed to `notes`, becomes optional, and is
rendered as a textarea; a new required `catalog_service` foreign key carries what the record is
about.

**Both foreign keys are `PROTECT`, never `CASCADE`.** Deleting a catalogue row while a deadline
points at it must fail loudly, because the alternative silently deletes deadlines, and a deleted
deadline is the exact failure this product exists to prevent. Deactivation is the supported
operation: the form offers only active rows, and a record already pointing at a deactivated row
keeps working, which is the entire point of deactivating instead of deleting. Ecobalance's 1.0
used `CASCADE` from service to sector and its 2.0 forbids that pattern; this file is on the 2.0
side of that line from birth.

**The fifteen rows arrive in a data migration**, generated with `makemigrations core --empty` and
then filled in, which is the framework-files rule of foundation section 12 applied to data. The
migration is a bootstrap and never the source of truth: once it has run, the catalogue is edited
through the administration site of foundation section 6. This is what I4 asks for, business values
living as data, and it is the opposite of `choices=` on the field, which would turn every rename by
the business into a schema migration. The catalogue changes often, and that frequency is itself a
requirement.

**The administration site registers `ServiceCategory` and `CatalogService`**, because the sentence
above is only true if a human has a screen. `core/admin.py` is empty today, so this is the first
registration in the project.

**Migrating the free text**, in this order, as separate generated migrations:

1. Rename `description` to `notes` and allow it to be blank.
2. Seed the catalogue.
3. Add `catalog_service` as nullable.
4. A data step that matches each existing row against the seeded catalogue by exact name and
   deletes the rows it cannot match.
5. Alter `catalog_service` to non-null.

Step 4 deletes data, and that is defensible for exactly one reason: no production database exists.
B11 is blocked on OQ-2, so every row on any disk today is development seed data. **If B11 ships
before B12 merges, step 4 is wrong** and must be replaced by a mapping the owner supplies. That
condition is written here rather than assumed, because a migration that quietly deletes production
rows is the worst thing in this file.

**Reading the catalogue costs a constant number of queries.** The form builds its options from one
ordered query over active rows joined to their category. The list view and the CSV export reach the
category and service names through `select_related`, never one row at a time. This is the
structural performance rule of foundation section 8, and at fifteen rows the point is the shape,
not the milliseconds.

## Consequences

`core/engine.py` renders `{service}` in the warning text from `service.description` today. It now
reads the catalogue name, and the run must select it in the same query as the records. The message
template contract of ADR 0001 is unchanged: `MESSAGE_TEMPLATE_FIELDS` keeps its four names and no
configured template breaks.

B10's CSV export gains a category column, a service column and the observation. The flat row
promise of foundation section 3 survives untouched, because a reference resolves to a name on the
way out.

Every test that constructs a `Service` with `description=` has to construct one with a catalogue
entry instead. That is roughly a dozen test modules and it is unavoidable: the model changed.

Amended 2026-08-28, during B12's Window A, which reported that `ServiceCategory.is_active` was a
column this document declared and then never gave a job. It has one now, stated above, and Window A
carries the test.

`ecobalance_service_id` is null in all fifteen rows on delivery and stays null until Ecobalance's
`catalog/` package exists and its SRV-1 question is answered. The column is the whole preparation;
the backfill is a later one line management command, not a redesign.
