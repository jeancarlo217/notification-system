"""Take one copy of the database and keep the most recent ones (foundation section 8).

The copy goes through SQLite's online backup API and never through a file copy, because copying
the file of a database a writer is inside can produce a torn, unopenable copy.
"""

import datetime
import sqlite3
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from core.backups import (
    BACKUP_RETENTION_COPIES,
    BackupError,
    backup_filename,
    copies_to_discard,
    copy_database,
)
from deadliner.config import get_backup_directory, get_config


class Command(BaseCommand):
    help = "Copy the database into the backup directory, keeping the most recent copies."

    def handle(self, *args: Any, **options: Any) -> None:
        directory = get_backup_directory()
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as refused:
            raise CommandError(
                f"The backup directory {directory} cannot be created: {refused}"
            ) from refused

        taken_at = datetime.datetime.now(tz=get_config().timezone)
        destination = directory / backup_filename(taken_at)
        try:
            copy_database(_source_connection(), destination)
        except (BackupError, sqlite3.Error, OSError) as failed:
            raise CommandError(
                f"The database was not copied to {destination}: {failed}"
            ) from failed

        discarded = _discard_old_copies(directory)
        self.stdout.write(f"Backup written to {destination}, {discarded} older copies discarded.")


def _source_connection() -> sqlite3.Connection:
    """The live connection Django is using, so the copy is of the database actually in service."""
    connection.ensure_connection()
    source = connection.connection
    if not isinstance(source, sqlite3.Connection):
        raise CommandError(
            "This command copies a SQLite database and the default database is not one."
        )
    return source


def _discard_old_copies(directory: Path) -> int:
    """Delete every copy beyond the retention limit, oldest first, and report how many went."""
    names = [entry.name for entry in directory.iterdir() if entry.is_file()]
    discarded = copies_to_discard(names, keep=BACKUP_RETENTION_COPIES)
    for name in discarded:
        (directory / name).unlink()
    return len(discarded)
