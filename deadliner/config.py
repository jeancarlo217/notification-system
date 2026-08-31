"""The single boundary between the environment and the application (backlog B2).

Every value the application takes from its environment is parsed and validated here, once, at
startup. Nothing else in the project reads ``os.environ``.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from string import Formatter
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

LANGUAGE_CODE = "pt-br"
USE_I18N = True

MESSAGE_TEMPLATE_FIELDS: frozenset[str] = frozenset(
    {"client", "service", "due_date", "days_remaining"}
)
"""The field names a warning template may reference (foundation section 4)."""

# Three, not sixteen: foundation section 6 v0.2 made the segment a short link meant to be sent to
# people, so the floor is only what the URL configuration can mount and a person can type.
SECRET_PATH_SEGMENT_MIN_LENGTH = 3
WHATSAPP_NUMBER_MIN_DIGITS = 8
WHATSAPP_NUMBER_MAX_DIGITS = 15

_URL_SAFE_SEGMENT = re.compile(r"[A-Za-z0-9_-]+")
_NUMBER_SEPARATORS = re.compile(r"[\s()+.-]")
_DEFAULT_DATABASE_PATH = "db.sqlite3"
_DEFAULT_BACKUP_DIRECTORY = "backups"
_FALLBACK_TIMEZONE = ZoneInfo("UTC")


class ConfigError(ImproperlyConfigured):
    """Raised when the environment does not describe a usable configuration.

    The message names every offending variable and reports them all at once. It never repeats
    the value of a secret, because the text reaches the logs (I5, I7).
    """


@dataclass(frozen=True, slots=True)
class DjangoConfig:
    """The infrastructure values the Django settings module consumes.

    ``database_path`` and ``backup_directory`` are verbatim from the environment; resolving a
    relative one against the project directory belongs to the settings module.
    """

    secret_key: str
    debug: bool
    allowed_hosts: tuple[str, ...]
    database_path: Path
    backup_directory: Path


@dataclass(frozen=True, slots=True)
class DeadlinerConfig:
    """The business values the product is defined by, never literals in code (I4).

    ``alert_thresholds`` is ordered from the earliest warning to the due date, and
    ``whatsapp_number`` holds digits only, country code first.
    """

    alert_thresholds: tuple[int, ...]
    whatsapp_number: str
    message_template: str
    secret_path_segment: str
    timezone: ZoneInfo


@dataclass(frozen=True, slots=True)
class Config:
    """Everything this application reads from its environment."""

    django: DjangoConfig
    deadliner: DeadlinerConfig


def load_config(env: Mapping[str, str]) -> Config:
    """Parse and validate an environment, or raise ``ConfigError`` naming every problem in it."""
    problems: list[str] = []

    # Each reader records its problem and returns a placeholder rather than stopping at the first
    # bad variable, so one run reports the whole list. No placeholder ever reaches a caller: a
    # non-empty `problems` raises below.
    debug = _read_debug(env, problems)
    django_config = DjangoConfig(
        secret_key=_read_secret_key(env, problems),
        debug=debug,
        allowed_hosts=_read_allowed_hosts(env, problems, debug=debug),
        database_path=_read_database_path(env),
        backup_directory=_read_backup_directory(env),
    )
    deadliner_config = DeadlinerConfig(
        alert_thresholds=_read_thresholds(env, problems),
        whatsapp_number=_read_whatsapp_number(env, problems),
        message_template=_read_message_template(env, problems),
        secret_path_segment=_read_secret_path_segment(env, problems),
        timezone=_read_timezone(env, problems),
    )

    if problems:
        listed = "\n".join(f"  {problem}" for problem in problems)
        raise ConfigError(f"The environment does not describe a usable configuration:\n{listed}")

    return Config(django=django_config, deadliner=deadliner_config)


def get_config() -> DeadlinerConfig:
    """The business configuration loaded at startup, typed for callers of Django settings."""
    config = getattr(settings, "DEADLINER", None)
    if not isinstance(config, DeadlinerConfig):
        raise ConfigError("settings.DEADLINER is missing or is not a DeadlinerConfig.")
    return config


def get_backup_directory() -> Path:
    """The directory the database copies land in, typed for callers of Django settings."""
    directory = getattr(settings, "BACKUP_DIRECTORY", None)
    if not isinstance(directory, Path):
        raise ConfigError("settings.BACKUP_DIRECTORY is missing or is not a Path.")
    return directory


def _read_secret_key(env: Mapping[str, str], problems: list[str]) -> str:
    value = env.get("DJANGO_SECRET_KEY", "").strip()
    if not value:
        problems.append("DJANGO_SECRET_KEY is required and must not be blank (I5).")
        return ""
    return value


def _read_debug(env: Mapping[str, str], problems: list[str]) -> bool:
    raw = env.get("DJANGO_DEBUG")
    if raw is None:
        return False
    if raw in {"0", "1"}:
        return raw == "1"
    problems.append(f'DJANGO_DEBUG must be "0" or "1", got {raw!r}.')
    return False


def _read_allowed_hosts(
    env: Mapping[str, str], problems: list[str], *, debug: bool
) -> tuple[str, ...]:
    raw = env.get("DJANGO_ALLOWED_HOSTS", "")
    hosts = tuple(host.strip() for host in raw.split(",") if host.strip())
    if not hosts and not debug:
        problems.append("DJANGO_ALLOWED_HOSTS must name a host when DJANGO_DEBUG is 0.")
    return hosts


def _read_database_path(env: Mapping[str, str]) -> Path:
    return Path(env.get("DJANGO_DATABASE_PATH", "").strip() or _DEFAULT_DATABASE_PATH)


def _read_backup_directory(env: Mapping[str, str]) -> Path:
    return Path(env.get("DJANGO_BACKUP_DIRECTORY", "").strip() or _DEFAULT_BACKUP_DIRECTORY)


def _read_thresholds(env: Mapping[str, str], problems: list[str]) -> tuple[int, ...]:
    raw = env.get("DEADLINER_ALERT_THRESHOLDS")
    if raw is None:
        problems.append("DEADLINER_ALERT_THRESHOLDS is required and has no default in code (I4).")
        return ()

    tokens = [token.strip() for token in raw.split(",")]
    if not all(token.isascii() and token.isdecimal() for token in tokens):
        problems.append(
            "DEADLINER_ALERT_THRESHOLDS must be whole numbers of days separated by commas, "
            f"got {raw!r}."
        )
        return ()

    days = [int(token) for token in tokens]
    if len(set(days)) != len(days):
        problems.append(f"DEADLINER_ALERT_THRESHOLDS must not repeat a threshold, got {raw!r}.")
        return ()
    return tuple(sorted(days, reverse=True))


def _read_whatsapp_number(env: Mapping[str, str], problems: list[str]) -> str:
    raw = env.get("DEADLINER_WHATSAPP_NUMBER")
    if raw is None:
        problems.append("DEADLINER_WHATSAPP_NUMBER is required and has no default in code (I4).")
        return ""

    digits = _NUMBER_SEPARATORS.sub("", raw.strip())
    within_range = WHATSAPP_NUMBER_MIN_DIGITS <= len(digits) <= WHATSAPP_NUMBER_MAX_DIGITS
    if not (digits.isascii() and digits.isdecimal() and within_range):
        problems.append(
            f"DEADLINER_WHATSAPP_NUMBER must be {WHATSAPP_NUMBER_MIN_DIGITS} to "
            f"{WHATSAPP_NUMBER_MAX_DIGITS} digits, country code first, got {raw!r}."
        )
        return ""
    return digits


def _read_message_template(env: Mapping[str, str], problems: list[str]) -> str:
    raw = env.get("DEADLINER_MESSAGE_TEMPLATE")
    if raw is None:
        problems.append("DEADLINER_MESSAGE_TEMPLATE is required and has no default in code (I4).")
        return ""
    if not raw.strip():
        problems.append("DEADLINER_MESSAGE_TEMPLATE must not be blank.")
        return ""

    try:
        fields = {name for _, name, _, _ in Formatter().parse(raw) if name is not None}
    except ValueError as malformed:
        problems.append(f"DEADLINER_MESSAGE_TEMPLATE is not a valid format string: {malformed}.")
        return ""

    unknown = sorted(fields - MESSAGE_TEMPLATE_FIELDS)
    if unknown:
        problems.append(
            f"DEADLINER_MESSAGE_TEMPLATE references {unknown}, and the fields a warning can "
            f"carry are {sorted(MESSAGE_TEMPLATE_FIELDS)}."
        )
        return ""
    return raw


def _read_secret_path_segment(env: Mapping[str, str], problems: list[str]) -> str:
    raw = env.get("DEADLINER_SECRET_PATH_SEGMENT")
    if raw is None:
        problems.append(
            "DEADLINER_SECRET_PATH_SEGMENT is required and has no default in code (I4)."
        )
        return ""

    value = raw.strip()
    if not _URL_SAFE_SEGMENT.fullmatch(value) or len(value) < SECRET_PATH_SEGMENT_MIN_LENGTH:
        # Alone among these messages this one omits the offending value, because the text reaches
        # the logs and I7 still stands (foundation section 6 v0.2 kept it).
        problems.append(
            f"DEADLINER_SECRET_PATH_SEGMENT must be at least {SECRET_PATH_SEGMENT_MIN_LENGTH} "
            "characters of A to Z, a to z, 0 to 9, underscore or hyphen."
        )
        return ""
    return value


def _read_timezone(env: Mapping[str, str], problems: list[str]) -> ZoneInfo:
    raw = env.get("DEADLINER_TIMEZONE")
    if raw is None:
        problems.append("DEADLINER_TIMEZONE is required and has no default in code (I4).")
        return _FALLBACK_TIMEZONE

    try:
        return ZoneInfo(raw.strip())
    # An unknown name raises KeyError; one that escapes the zone directory raises ValueError.
    except (KeyError, ValueError):
        problems.append(f"DEADLINER_TIMEZONE must be an IANA time zone name, got {raw!r}.")
        return _FALLBACK_TIMEZONE
