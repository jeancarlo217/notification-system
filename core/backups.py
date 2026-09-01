"""Copies of the one file the company owns (foundation sections 2 and 8).

Everything the business has is the SQLite file on the ``data`` volume, so a copy of it is the
only thing standing between a destroyed volume and a lost registry. The naming and the retention
here are pure decisions, plain data in and plain data out; the copy is the single effect and takes
a connection rather than a path, so a test drives it with any sqlite3 database (specs/testing.md).
"""

import datetime
import os
import re
import sqlite3
from collections.abc import Iterable
from pathlib import Path

BACKUP_RETENTION_COPIES = 14
"""How many copies a backup directory keeps: two weeks of daily copies, long enough for a bad
migration or a mistaken delete to be noticed and reported over a holiday, and small enough that a
directory of a database this size stays in the megabytes."""

_TIMESTAMP_FORMAT = "%Y-%m-%dT%H-%M-%S"
_COPY_NAME = re.compile(r"db-\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}\.sqlite3")


class BackupError(Exception):
    """A copy that cannot be taken, reported rather than attempted."""


def backup_filename(moment: datetime.datetime) -> str:
    """The name a copy taken at ``moment`` carries: sortable as text, readable by a human.

    The ``.sqlite3`` suffix is the one the repository already refuses to track (I5).
    """
    return f"db-{moment.strftime(_TIMESTAMP_FORMAT)}.sqlite3"


def copies_to_discard(filenames: Iterable[str], *, keep: int) -> tuple[str, ...]:
    """The names a directory keeping the ``keep`` most recent copies no longer needs, oldest first.

    Only names this module writes are ever returned, so everything else in the directory is safe.
    """
    if keep < 1:
        raise ValueError(f"A backup directory keeps at least one copy, and keep is {keep}.")
    copies = sorted(name for name in filenames if _COPY_NAME.fullmatch(name))
    return tuple(copies[: max(len(copies) - keep, 0)])


def copy_database(source: sqlite3.Connection, destination: Path) -> None:
    """Copy the whole of ``source`` to ``destination`` as a consistent database, or raise.

    Uses SQLite's online backup API in one step, which holds a read lock for the copy and yields a
    snapshot; copying the file of a live database instead can tear it mid transaction.
    """
    # Measured on CPython 3.13.15 with SQLite 3.51.2: a source holding its own write transaction
    # makes backup() retry a locked handle forever, in a C loop no signal reaches. Refusing keeps
    # the failure visible (foundation section 0.5).
    if source.in_transaction:
        raise BackupError(
            "The database connection is inside a transaction, and a copy taken from it would "
            "wait forever on a lock that connection holds itself."
        )

    # Checked before the attempt so the failure names the directory rather than arriving as
    # SQLite's `unable to open database file`, which reads like a corrupt database and is not one.
    # A repository cloned by root leaves a bind mounted directory owned by root while the container
    # runs as another user, which is how the first real deployment met this (foundation 0.5).
    directory = destination.parent
    if not os.access(directory, os.W_OK | os.X_OK):
        raise BackupError(
            f"The backup directory {directory} is not writable by the user this process runs as "
            f"(uid {os.geteuid()}), so no copy can be taken. Give that directory to that user on "
            f"the host; a repository cloned by root leaves it owned by root."
        )

    # Written beside the destination and named only once it is whole, because a half written file
    # under a backup name is a restore that silently loses everything (foundation section 0.5).
    partial = destination.with_name(f".{destination.name}")
    try:
        target = sqlite3.connect(partial)
        try:
            source.backup(target)
        finally:
            target.close()
        partial.replace(destination)
    finally:
        partial.unlink(missing_ok=True)
