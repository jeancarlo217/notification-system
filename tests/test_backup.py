"""The database backup: a copy of the one file the company owns, and a way to put it back.

Traces: foundation section 2 (the truth lives in persisted records, so losing the file is losing
the company's deadlines), section 8 (SQLite on a Docker volume), section 0.5 (nothing fails
silently, which for a backup means a copy that cannot be taken says so instead of hanging or
leaving half a file behind), and I5 (a backup is production data and must never be committable).

The naming and the retention are pure decisions and are tested with no filesystem and no clock.
The copy is the one effect, tested against plain sqlite3 connections, and the command is the thin
shell that wires the two together (specs/testing.md).
"""

import dataclasses
import datetime
import sqlite3
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from core.backups import (
    BACKUP_RETENTION_COPIES,
    BackupError,
    backup_filename,
    copies_to_discard,
    copy_database,
)
from deadliner.config import ConfigError, DeadlinerConfig, get_backup_directory, load_config
from tests.builders import a_service

TEST_DEADLINER = DeadlinerConfig(
    alert_thresholds=(30, 7, 0),
    whatsapp_number="5567999998888",
    message_template="{client}|{service}|{due_date}|{days_remaining}",
    secret_path_segment="fake-segment-for-tests",
    timezone=ZoneInfo("America/Campo_Grande"),
)

VALID_ENV = {
    "DJANGO_SECRET_KEY": "placeholder-value-for-tests-only",
    "DJANGO_DEBUG": "0",
    "DJANGO_ALLOWED_HOSTS": "prazos.example.com",
    "DEADLINER_ALERT_THRESHOLDS": "30,7,0",
    "DEADLINER_WHATSAPP_NUMBER": "5567999998888",
    "DEADLINER_MESSAGE_TEMPLATE": "{client}: {service} vence em {days_remaining} dias.",
    "DEADLINER_SECRET_PATH_SEGMENT": "prazos",
    "DEADLINER_TIMEZONE": "America/Campo_Grande",
}


def a_database(path: Path, *clients: str) -> sqlite3.Connection:
    """A SQLite database at ``path`` holding one row per client, committed, left open."""
    connection = sqlite3.connect(path)
    connection.execute("create table client (id integer primary key, name text)")
    connection.executemany("insert into client (name) values (?)", [(name,) for name in clients])
    connection.commit()
    return connection


def clients_in(path: Path) -> list[str]:
    """The client names a database file holds, read back through a fresh connection."""
    connection = sqlite3.connect(path)
    try:
        return [row[0] for row in connection.execute("select name from client order by name")]
    finally:
        connection.close()


def copies_in(directory: Path) -> list[Path]:
    """The backup copies a directory holds, oldest first."""
    return sorted(directory.glob("db-*.sqlite3"))


def a_moment(hour: int = 14, minute: int = 5, second: int = 0) -> datetime.datetime:
    """A fixed moment, so a naming test never reads a clock."""
    return datetime.datetime(2026, 8, 31, hour, minute, second, tzinfo=ZoneInfo("UTC"))


def test_a_copy_is_named_by_the_moment_it_was_taken() -> None:
    """The backup task: a human reading the directory can tell which copy is which."""
    assert backup_filename(a_moment()) == "db-2026-08-31T14-05-00.sqlite3"


def test_copies_sort_as_text_in_the_order_they_were_taken() -> None:
    """The backup task: retention and a human both order the directory by name alone."""
    names = [backup_filename(a_moment(hour=hour)) for hour in (9, 14, 23)]

    assert sorted(names) == names


def test_a_copy_is_named_so_the_repository_refuses_to_track_it() -> None:
    """I5: a backup is production data, and the tree already ignores every .sqlite3 file."""
    assert backup_filename(a_moment()).endswith(".sqlite3")


def test_retention_discards_every_copy_beyond_the_most_recent_ones() -> None:
    """The backup task: the directory keeps a bounded number of copies, the newest ones."""
    names = [backup_filename(a_moment(hour=hour)) for hour in (9, 14, 23)]

    assert copies_to_discard(names, keep=1) == (names[0], names[1])


def test_retention_discards_nothing_while_the_directory_is_within_its_limit() -> None:
    """The backup task: a fresh installation loses nothing to retention."""
    names = [backup_filename(a_moment(hour=hour)) for hour in (9, 14)]

    assert copies_to_discard(names, keep=BACKUP_RETENTION_COPIES) == ()


def test_retention_never_discards_a_file_it_did_not_write() -> None:
    """The backup task: the directory is a place a person keeps things, not this command's own."""
    names = ["notes.txt", ".gitkeep", "db.sqlite3", backup_filename(a_moment())]

    assert copies_to_discard(names, keep=1) == ()


def test_retention_refuses_to_keep_nothing() -> None:
    """Foundation section 0.5: a limit that would delete the copy just taken fails loudly."""
    with pytest.raises(ValueError):
        copies_to_discard([backup_filename(a_moment())], keep=0)


def test_a_copy_opens_as_a_database_and_carries_the_rows_that_were_there(tmp_path: Path) -> None:
    """The backup task: the copy is a database, not a file that resembles one."""
    source = a_database(tmp_path / "live.sqlite3", "Fazenda Boa Vista")

    copy_database(source, tmp_path / "copy.sqlite3")
    source.close()

    assert clients_in(tmp_path / "copy.sqlite3") == ["Fazenda Boa Vista"]


def test_a_copy_taken_while_another_connection_writes_holds_the_committed_rows(
    tmp_path: Path,
) -> None:
    """The backup task: this is why the copy goes through SQLite's online backup API and never
    through a file copy, which mid transaction yields a torn file that may not open at all."""
    source = a_database(tmp_path / "live.sqlite3", "Fazenda Boa Vista")
    writer = sqlite3.connect(tmp_path / "live.sqlite3")
    writer.execute("insert into client (name) values ('never committed')")

    copy_database(source, tmp_path / "copy.sqlite3")
    writer.rollback()
    writer.close()
    source.close()

    assert clients_in(tmp_path / "copy.sqlite3") == ["Fazenda Boa Vista"]


def test_a_copy_from_a_connection_inside_its_own_transaction_is_refused(tmp_path: Path) -> None:
    """Foundation section 0.5: measured on CPython 3.13.15 with SQLite 3.51.2, that copy waits
    forever on a lock the source connection holds itself, and the wait takes no signal. A daily
    job that hangs is exactly the silent failure this product refuses."""
    source = a_database(tmp_path / "live.sqlite3", "Fazenda Boa Vista")
    source.execute("insert into client (name) values ('uncommitted')")

    with pytest.raises(BackupError):
        copy_database(source, tmp_path / "copy.sqlite3")

    source.rollback()
    source.close()


def test_a_copy_that_could_not_be_taken_leaves_no_file_under_a_backup_name(
    tmp_path: Path,
) -> None:
    """Foundation section 0.5: a half written file under a backup name is a restore that loses
    everything, and it would fail on the day it is needed."""
    source = a_database(tmp_path / "live.sqlite3", "Fazenda Boa Vista")
    source.execute("insert into client (name) values ('uncommitted')")
    destination = tmp_path / backup_filename(a_moment())

    with pytest.raises(BackupError):
        copy_database(source, destination)

    source.rollback()
    source.close()
    assert list(tmp_path.iterdir()) == [tmp_path / "live.sqlite3"]


def test_restoring_a_copy_puts_back_exactly_what_was_taken(tmp_path: Path) -> None:
    """The backup task: restoring is putting the file back over a database nothing is writing
    to, which is what ``just restore`` does once the writers are stopped."""
    live = tmp_path / "live.sqlite3"
    source = a_database(live, "Fazenda Boa Vista", "Sitio Sao Jose")
    copy_database(source, tmp_path / "copy.sqlite3")
    source.execute("delete from client where name = 'Sitio Sao Jose'")
    source.commit()
    source.close()

    live.write_bytes((tmp_path / "copy.sqlite3").read_bytes())

    assert clients_in(live) == ["Fazenda Boa Vista", "Sitio Sao Jose"]


def test_the_backup_directory_is_read_from_the_environment() -> None:
    """ADR 0001: the copies land where the deployment says, and nothing outside the boundary
    reads the environment."""
    config = load_config({**VALID_ENV, "DJANGO_BACKUP_DIRECTORY": "/backups"})

    assert config.django.backup_directory == Path("/backups")


def test_the_backup_directory_falls_back_to_a_project_default() -> None:
    """ADR 0001: the directory is infrastructure like the database path, not one of the five
    business values I4 names, so a default in code is honest."""
    config = load_config(VALID_ENV)

    assert config.django.backup_directory == Path("backups")


def test_a_missing_backup_directory_setting_is_an_error_and_never_a_none() -> None:
    """ADR 0001: application code reads its configuration through a typed accessor."""
    with override_settings(BACKUP_DIRECTORY=None), pytest.raises(ConfigError):
        get_backup_directory()


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
@override_settings(DEADLINER=TEST_DEADLINER)
def test_the_command_writes_a_copy_carrying_the_registered_records(tmp_path: Path) -> None:
    """Foundation section 2: what the copy must hold is the persisted records themselves."""
    a_service(client="Fazenda Boa Vista")

    with override_settings(BACKUP_DIRECTORY=tmp_path):
        call_command("backup_database")

    connection = sqlite3.connect(copies_in(tmp_path)[-1])
    try:
        clients = [row[0] for row in connection.execute("select client from core_service")]
    finally:
        connection.close()
    assert clients == ["Fazenda Boa Vista"]


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
@override_settings(DEADLINER=TEST_DEADLINER)
def test_the_command_creates_the_backup_directory_when_it_is_missing(tmp_path: Path) -> None:
    """The backup task: a first run on a fresh host takes a copy instead of reporting a path."""
    directory = tmp_path / "backups"

    with override_settings(BACKUP_DIRECTORY=directory):
        call_command("backup_database")

    assert len(copies_in(directory)) == 1


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
@override_settings(DEADLINER=TEST_DEADLINER)
def test_the_command_reports_a_directory_it_cannot_create(tmp_path: Path) -> None:
    """Foundation section 0.5: a backup that cannot be written says so, and says where."""
    blocked = tmp_path / "file"
    blocked.write_text("not a directory", encoding="utf-8")

    with (
        override_settings(BACKUP_DIRECTORY=blocked / "backups"),
        pytest.raises(CommandError) as refused,
    ):
        call_command("backup_database")

    assert str(blocked) in str(refused.value)


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
@override_settings(DEADLINER=TEST_DEADLINER)
def test_the_command_discards_the_copies_beyond_the_retention_limit(tmp_path: Path) -> None:
    """The backup task: the directory holds the most recent copies and does not grow forever."""
    older = [
        tmp_path / backup_filename(datetime.datetime(2026, 1, 1, 3, 0, second))
        for second in range(BACKUP_RETENTION_COPIES + 2)
    ]
    for copy in older:
        copy.touch()

    with override_settings(BACKUP_DIRECTORY=tmp_path):
        call_command("backup_database")

    remaining = [path.name for path in copies_in(tmp_path)]
    assert len(remaining) == BACKUP_RETENTION_COPIES
    assert older[0].name not in remaining
    assert older[-1].name in remaining


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_the_command_names_the_copy_in_the_configured_time_zone(tmp_path: Path) -> None:
    """Foundation section 5: one configured zone decides what the clock reads, here as in the
    daily run. The bounds are read in that zone, so a name taken from any other zone falls
    outside them."""
    zone = ZoneInfo("Pacific/Kiritimati")
    configured = dataclasses.replace(TEST_DEADLINER, timezone=zone)

    with override_settings(DEADLINER=configured, BACKUP_DIRECTORY=tmp_path):
        before = backup_filename(datetime.datetime.now(tz=zone))
        call_command("backup_database")
        after = backup_filename(datetime.datetime.now(tz=zone))

    assert before <= copies_in(tmp_path)[-1].name <= after
