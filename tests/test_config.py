"""B2, the configuration surface: the single boundary between the environment and the app.

Derives from I4 (business values are data, never literals in code), I5 (no credential has a
default and the real environment file is untracked) and I7 (a secret never reaches the logs).

B26 widened it: the destination is a WhatsApp group or a number in one variable, and the gateway
the adapter of B8 will speak to enters here too (foundation section 4 v0.4, ADR 0001).

B27 moved it again (foundation v0.6, the notes of 2026-10-27 and 2026-11-09 in ADR 0001): the
thresholds are gone, the send time arrives, and the message is a header, a line and five deadline
phrases.
"""

import datetime
import os
from pathlib import Path

import pytest
from django.conf import settings
from django.test import override_settings

from deadliner.config import (
    DEADLINE_PHRASE_FIELDS,
    MESSAGE_HEADER_FIELDS,
    MESSAGE_TEMPLATE_FIELDS,
    Config,
    ConfigError,
    DeadlinerConfig,
    EvolutionConfig,
    get_config,
    get_evolution_config,
    load_config,
)

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent

VALID_ENV = {
    "DJANGO_SECRET_KEY": "placeholder-value-for-tests-only",
    "DJANGO_DEBUG": "0",
    "DJANGO_ALLOWED_HOSTS": "prazos.example.com",
    "DJANGO_DATABASE_PATH": "db.sqlite3",
    "DEADLINER_SEND_TIME": "07:00",
    "DEADLINER_WHATSAPP_DESTINATION": "5567999998888",
    "DEADLINER_MESSAGE_HEADER": "Serviços em aberto, {date:%d/%m/%Y}. {count} nesta lista.",
    "DEADLINER_MESSAGE_TEMPLATE": "• *{client}* | {service} | {deadline} ({due_date:%d/%m/%Y})",
    "DEADLINER_DEADLINE_FUTURE": "vence em {days} dias",
    "DEADLINER_DEADLINE_TOMORROW": "vence amanhã",
    "DEADLINER_DEADLINE_TODAY": "vence hoje",
    "DEADLINER_DEADLINE_YESTERDAY": "venceu ontem",
    "DEADLINER_DEADLINE_OVERDUE": "venceu há {days} dias",
    "DEADLINER_SECRET_PATH_SEGMENT": "abcdefghijklmnop",
    "DEADLINER_TIMEZONE": "America/Campo_Grande",
}

EVOLUTION_ENV = {
    "EVOLUTION_BASE_URL": "http://evolution:8080",
    "EVOLUTION_INSTANCE_NAME": "valeverde",
    "EVOLUTION_API_KEY": "placeholder-value-for-tests-only",
}

DEADLINE_PHRASE_VARIABLES = [
    "DEADLINER_DEADLINE_FUTURE",
    "DEADLINER_DEADLINE_TOMORROW",
    "DEADLINER_DEADLINE_TODAY",
    "DEADLINER_DEADLINE_YESTERDAY",
    "DEADLINER_DEADLINE_OVERDUE",
]

BUSINESS_VARIABLES = [
    "DEADLINER_SEND_TIME",
    "DEADLINER_WHATSAPP_DESTINATION",
    "DEADLINER_MESSAGE_HEADER",
    "DEADLINER_MESSAGE_TEMPLATE",
    *DEADLINE_PHRASE_VARIABLES,
    "DEADLINER_SECRET_PATH_SEGMENT",
    "DEADLINER_TIMEZONE",
]


def env_with(**overrides: str) -> dict[str, str]:
    """A valid environment with the named variables replaced."""
    return {**VALID_ENV, **overrides}


def env_without(name: str) -> dict[str, str]:
    """A valid environment with one variable removed."""
    return {key: value for key, value in VALID_ENV.items() if key != name}


def parse_env_file(path: Path) -> dict[str, str]:
    """The key-value pairs of a dotenv file, ignoring comments and blank lines."""
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        name, _, value = stripped.partition("=")
        values[name.strip()] = value.strip()
    return values


def test_the_send_time_is_read_from_the_environment() -> None:
    """I4: the hour the list is owed from is configuration, never a literal in code."""
    config = load_config(env_with(DEADLINER_SEND_TIME="07:00"))

    assert config.deadliner.send_time == datetime.time(7, 0)


def test_two_send_time_configurations_differ_with_no_code_change() -> None:
    """I4: its acceptance test at this layer; the schedule decision carries the other half."""
    company_schedule = load_config(env_with(DEADLINER_SEND_TIME="07:00"))
    other_schedule = load_config(env_with(DEADLINER_SEND_TIME="18:45"))

    assert company_schedule.deadliner.send_time == datetime.time(7, 0)
    assert other_schedule.deadliner.send_time == datetime.time(18, 45)


def test_the_send_time_carries_no_zone_of_its_own() -> None:
    """ADR 0001, note of 2026-11-09: the time is read in `DEADLINER_TIMEZONE`, so the value
    itself is a wall clock reading with no zone attached."""
    config = load_config(env_with(DEADLINER_SEND_TIME="07:00"))

    assert config.deadliner.send_time.tzinfo is None


@pytest.mark.parametrize(
    "value",
    ["", "   ", "7:00", "07:00:00", "24:00", "07:60", "7", "0700", "07h00", "sete", "07:00 AM"],
)
def test_a_send_time_that_is_not_a_24_hour_hh_mm_is_rejected(value: str) -> None:
    """ADR 0001, note of 2026-11-09: a value that half parses is the one nobody notices is
    wrong, so `7:00` is an error and not seven o'clock."""
    with pytest.raises(ConfigError, match="DEADLINER_SEND_TIME"):
        load_config(env_with(DEADLINER_SEND_TIME=value))


def test_a_leftover_threshold_variable_is_ignored() -> None:
    """ADR 0001, note of 2026-11-09: a live `.env` still carrying the removed variable boots
    unchanged, because an unknown variable is not read."""
    config = load_config(env_with(DEADLINER_ALERT_THRESHOLDS="30,7,0"))

    assert isinstance(config, Config)


@pytest.mark.parametrize(
    "value",
    ["+55 67 99999-8888", "55 (67) 99999.8888", "+5567999998888", "5567999998888"],
)
def test_a_destination_number_is_stored_as_digits_only(value: str) -> None:
    """I4: a number destination is kept in the form every vendor format adds to."""
    config = load_config(env_with(DEADLINER_WHATSAPP_DESTINATION=value))

    assert config.deadliner.whatsapp_destination == "5567999998888"


def test_a_group_identifier_is_kept_verbatim() -> None:
    """Foundation section 4 v0.4: the warnings go to a group, and its identifier is the vendor's
    own string, read from Evolution and never typed or reshaped."""
    config = load_config(env_with(DEADLINER_WHATSAPP_DESTINATION="120363123456789012@g.us"))

    assert config.deadliner.whatsapp_destination == "120363123456789012@g.us"


def test_one_variable_carries_either_destination() -> None:
    """I4: two deployments, two destinations, no code change, and no rule about which wins."""
    group = load_config(env_with(DEADLINER_WHATSAPP_DESTINATION="120363123456789012@g.us"))
    number = load_config(env_with(DEADLINER_WHATSAPP_DESTINATION="5567999998888"))

    assert group.deadliner.whatsapp_destination == "120363123456789012@g.us"
    assert number.deadliner.whatsapp_destination == "5567999998888"


@pytest.mark.parametrize(
    "value",
    [
        "",
        "1234567",
        "1234567890123456",
        "55679999a8888",
        "abc",
        "@g.us",
        "grupo@g.us",
        "5567999998888@s.whatsapp.net",
        "120363123456789012@g.us extra",
    ],
)
def test_a_destination_that_is_neither_a_number_nor_a_group_is_rejected(value: str) -> None:
    """B2: E.164 allows 8 to 15 digits, a group is digits and `@g.us`, and nothing else is a
    destination the gateway could deliver to."""
    with pytest.raises(ConfigError, match="DEADLINER_WHATSAPP_DESTINATION"):
        load_config(env_with(DEADLINER_WHATSAPP_DESTINATION=value))


def test_the_message_template_is_read_from_the_environment() -> None:
    """I4: the wording of one line of the list is configuration (foundation section 4)."""
    template = "• *{client}* | {service} | {deadline} ({due_date:%d/%m/%Y}) {days_remaining}"
    config = load_config(env_with(DEADLINER_MESSAGE_TEMPLATE=template))

    assert config.deadliner.message_template == template


def test_a_template_may_use_only_some_of_the_allowed_fields() -> None:
    """B2: validation stays quiet when the owner's wording is simply shorter."""
    config = load_config(env_with(DEADLINER_MESSAGE_TEMPLATE="{service} vence em {due_date}."))

    assert config.deadliner.message_template == "{service} vence em {due_date}."


def test_a_template_may_carry_escaped_braces_as_literal_text() -> None:
    """B2: an escaped brace is text, not a field, and must not be read as one."""
    config = load_config(env_with(DEADLINER_MESSAGE_TEMPLATE="{{aviso}} para {client}"))

    assert config.deadliner.message_template == "{{aviso}} para {client}"


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        "{cliente} vence",
        "{client",
        "cliente}",
        "{cli{ent}",
        "{} vence",
        "{0} vence",
        "{client.upper} vence",
        "{client[0]} vence",
        "{count} servicos",
    ],
)
def test_a_template_the_engine_could_not_render_is_rejected(value: str) -> None:
    """B2: a wording defect is caught at startup, never at send time in the daily run."""
    with pytest.raises(ConfigError, match="DEADLINER_MESSAGE_TEMPLATE"):
        load_config(env_with(DEADLINER_MESSAGE_TEMPLATE=value))


def test_the_line_contract_is_the_five_fields_the_canon_names() -> None:
    """I4, ADR 0001 note of 2026-10-27: the four fields the record provides and `deadline`, the
    one the engine computes."""
    assert {
        "client",
        "service",
        "due_date",
        "days_remaining",
        "deadline",
    } == MESSAGE_TEMPLATE_FIELDS


def test_the_message_header_is_read_from_the_environment() -> None:
    """I4: what heads the list is configuration (foundation section 4)."""
    header = "Serviços em aberto, {date:%d/%m/%Y}. {count} serviços nesta lista."
    config = load_config(env_with(DEADLINER_MESSAGE_HEADER=header))

    assert config.deadliner.message_header == header


def test_a_header_may_use_no_field_at_all() -> None:
    """ADR 0001: validation stays quiet when the owner's header is plain text."""
    config = load_config(env_with(DEADLINER_MESSAGE_HEADER="Serviços em aberto"))

    assert config.deadliner.message_header == "Serviços em aberto"


@pytest.mark.parametrize("value", ["", "   ", "{client} em aberto", "{count", "{} servicos"])
def test_a_header_the_engine_could_not_render_is_rejected(value: str) -> None:
    """ADR 0001, note of 2026-09-02: the header is validated like the line, over its own
    fields, so a field of the line is an error in it."""
    with pytest.raises(ConfigError, match="DEADLINER_MESSAGE_HEADER"):
        load_config(env_with(DEADLINER_MESSAGE_HEADER=value))


def test_the_header_contract_is_the_count_and_the_date() -> None:
    """I4, ADR 0001: the two fields a header may reference."""
    assert {"count", "date"} == MESSAGE_HEADER_FIELDS


def test_the_five_deadline_phrases_are_read_from_the_environment() -> None:
    """I4, foundation section 4: the five phrases are the owner's voice, so they are data."""
    config = load_config(VALID_ENV)

    phrases = config.deadliner.deadline_phrases

    assert phrases.future == "vence em {days} dias"
    assert phrases.tomorrow == "vence amanhã"
    assert phrases.today == "vence hoje"
    assert phrases.yesterday == "venceu ontem"
    assert phrases.overdue == "venceu há {days} dias"


@pytest.mark.parametrize("name", DEADLINE_PHRASE_VARIABLES)
@pytest.mark.parametrize("value", ["", "   ", "vence em {dias} dias", "{days", "{days_remaining}"])
def test_a_deadline_phrase_the_engine_could_not_render_is_rejected(name: str, value: str) -> None:
    """ADR 0001, note of 2026-10-27: each phrase is a format string over the single field
    `days`, and anything else is caught at startup."""
    with pytest.raises(ConfigError, match=name):
        load_config(env_with(**{name: value}))


def test_the_phrase_contract_is_the_single_field_days() -> None:
    """I4, ADR 0001 note of 2026-10-27: a phrase is handed a count and nothing else."""
    assert {"days"} == DEADLINE_PHRASE_FIELDS


def test_the_path_segment_is_read_from_the_environment() -> None:
    """I4: the segment the application is served under is configuration and never a literal."""
    config = load_config(env_with(DEADLINER_SECRET_PATH_SEGMENT="qazwsxedcrfvtgby"))

    assert config.deadliner.secret_path_segment == "qazwsxedcrfvtgby"


def test_a_short_segment_is_accepted_because_the_link_is_meant_to_be_sent() -> None:
    """Foundation section 6 v0.2: the owner asked for a link short enough to send and type."""
    config = load_config(env_with(DEADLINER_SECRET_PATH_SEGMENT="vale"))

    assert config.deadliner.secret_path_segment == "vale"


def test_a_segment_of_the_minimum_length_is_accepted() -> None:
    """Foundation section 6 v0.2: three characters is the floor itself, not a value above it."""
    config = load_config(env_with(DEADLINER_SECRET_PATH_SEGMENT="vvs"))

    assert config.deadliner.secret_path_segment == "vvs"


@pytest.mark.parametrize(
    "value",
    [
        "",
        "vv",
        "with/a/slash/xyz",
        "with a space xyz",
        "with%percent%xyz",
        "segment-with-café-x",
    ],
)
def test_a_segment_that_is_not_a_url_safe_path_element_is_rejected(value: str) -> None:
    """Foundation section 6 v0.2: the floor is not secrecy any more, it is a value the URL
    configuration can mount and a person can type."""
    with pytest.raises(ConfigError, match="DEADLINER_SECRET_PATH_SEGMENT"):
        load_config(env_with(DEADLINER_SECRET_PATH_SEGMENT=value))


def test_the_timezone_is_read_from_the_environment() -> None:
    """I4: the zone that decides what today is, is configuration (foundation section 5)."""
    config = load_config(env_with(DEADLINER_TIMEZONE="America/Campo_Grande"))

    assert config.deadliner.timezone.key == "America/Campo_Grande"


@pytest.mark.parametrize("value", ["", "Mars/Olympus_Mons", "../../etc/passwd", "BRT"])
def test_a_timezone_the_standard_library_cannot_resolve_is_rejected(value: str) -> None:
    """B2: an unknown key raises KeyError and an escaping key raises ValueError, both are errors."""
    with pytest.raises(ConfigError, match="DEADLINER_TIMEZONE"):
        load_config(env_with(DEADLINER_TIMEZONE=value))


@pytest.mark.parametrize("name", BUSINESS_VARIABLES)
def test_no_business_value_has_a_default_in_code(name: str) -> None:
    """I4: a default in code is a literal in code, which is what the invariant forbids."""
    with pytest.raises(ConfigError, match=name):
        load_config(env_without(name))


def test_the_django_secret_key_is_read_from_the_environment() -> None:
    """I5: the key reaches Django from the environment and from nowhere else."""
    config = load_config(env_with(DJANGO_SECRET_KEY="placeholder-value-for-tests-only"))

    assert config.django.secret_key == "placeholder-value-for-tests-only"


def test_the_django_secret_key_is_required() -> None:
    """I5: no credential has a default, so none can be shipped by accident."""
    with pytest.raises(ConfigError, match="DJANGO_SECRET_KEY"):
        load_config(env_without("DJANGO_SECRET_KEY"))


def test_a_blank_django_secret_key_is_rejected() -> None:
    """I5: an empty value is an unset value wearing a disguise."""
    with pytest.raises(ConfigError, match="DJANGO_SECRET_KEY"):
        load_config(env_with(DJANGO_SECRET_KEY="   "))


def test_debug_is_off_when_the_environment_does_not_ask_for_it() -> None:
    """B2: the safe direction is the default."""
    config = load_config(env_without("DJANGO_DEBUG"))

    assert config.django.debug is False


def test_debug_is_on_when_the_environment_asks_for_it() -> None:
    """B2: one value turns it on, and it is spelled out in .env.example."""
    config = load_config(env_with(DJANGO_DEBUG="1"))

    assert config.django.debug is True


@pytest.mark.parametrize("value", ["true", "True", "yes", "on", "2", ""])
def test_an_ambiguous_debug_flag_is_rejected_rather_than_read_as_off(value: str) -> None:
    """B2: reading 'true' as off hides a misconfiguration instead of reporting it."""
    with pytest.raises(ConfigError, match="DJANGO_DEBUG"):
        load_config(env_with(DJANGO_DEBUG=value))


def test_allowed_hosts_are_split_and_stripped() -> None:
    """B2: the environment carries one comma-separated string, the settings need a sequence."""
    config = load_config(env_with(DJANGO_ALLOWED_HOSTS=" prazos.example.com , localhost ,"))

    assert config.django.allowed_hosts == ("prazos.example.com", "localhost")


def test_a_deployment_with_debug_off_must_name_its_hosts() -> None:
    """B2: an empty list with debug off refuses every request, so it is caught at startup."""
    with pytest.raises(ConfigError, match="DJANGO_ALLOWED_HOSTS"):
        load_config(env_with(DJANGO_DEBUG="0", DJANGO_ALLOWED_HOSTS=""))


def test_development_may_leave_the_hosts_empty() -> None:
    """B2: with debug on Django serves localhost by itself, so the check stays quiet."""
    config = load_config(env_with(DJANGO_DEBUG="1", DJANGO_ALLOWED_HOSTS=""))

    assert config.django.allowed_hosts == ()


def test_the_database_path_falls_back_to_the_project_default() -> None:
    """B2: the database file is infrastructure, not a business value, so a default is honest."""
    config = load_config(env_without("DJANGO_DATABASE_PATH"))

    assert config.django.database_path == Path("db.sqlite3")


def test_the_database_path_is_read_from_the_environment() -> None:
    """B2: Compose points it at the mounted volume (foundation section 8)."""
    config = load_config(env_with(DJANGO_DATABASE_PATH="/data/db.sqlite3"))

    assert config.django.database_path == Path("/data/db.sqlite3")


def test_the_gateway_the_adapter_speaks_to_is_read_from_the_environment() -> None:
    """B26: the Evolution values are infrastructure and enter through this boundary, because
    nothing else in this project reads os.environ (ADR 0001)."""
    config = load_config(env_with(**EVOLUTION_ENV))

    assert config.django.evolution == EvolutionConfig(
        base_url="http://evolution:8080",
        instance_name="valeverde",
        api_key="placeholder-value-for-tests-only",
    )


def test_an_environment_with_no_gateway_loads_and_configures_none() -> None:
    """B26: phase one runs with no WhatsApp at all, so an unconfigured gateway is a running
    application without one, never a refusal to start."""
    config = load_config(env_with())

    assert config.django.evolution is None


@pytest.mark.parametrize("missing", sorted(EVOLUTION_ENV))
def test_a_half_configured_gateway_is_rejected_and_names_what_is_missing(missing: str) -> None:
    """B26: two of the three values describe a gateway no adapter can reach, and an application
    that starts on them fails at send time instead of at startup."""
    present = {name: value for name, value in EVOLUTION_ENV.items() if name != missing}

    with pytest.raises(ConfigError, match=missing):
        load_config(env_with(**present))


@pytest.mark.parametrize(
    "value",
    ["", "   ", "evolution:8080", "ftp://evolution:8080", "http://", "//evolution:8080"],
)
def test_a_base_url_that_is_not_an_http_gateway_is_rejected(value: str) -> None:
    """B26: the adapter joins paths onto this value, so a string that is not an http origin is
    caught at startup rather than at three in the morning."""
    with pytest.raises(ConfigError, match="EVOLUTION_BASE_URL"):
        load_config(env_with(**{**EVOLUTION_ENV, "EVOLUTION_BASE_URL": value}))


def test_the_base_url_is_stored_without_its_trailing_slash() -> None:
    """B26: the adapter writes `/message/sendText/...` onto it, and `//` is a different path."""
    config = load_config(
        env_with(**{**EVOLUTION_ENV, "EVOLUTION_BASE_URL": "http://evolution:8080/"})
    )

    assert config.django.evolution is not None
    assert config.django.evolution.base_url == "http://evolution:8080"


@pytest.mark.parametrize("value", ["", "   ", "vale verde", "vale/verde", "vale?verde"])
def test_an_instance_name_that_is_not_a_url_path_element_is_rejected(value: str) -> None:
    """B26: the instance name is the last segment of every gateway call."""
    with pytest.raises(ConfigError, match="EVOLUTION_INSTANCE_NAME"):
        load_config(env_with(**{**EVOLUTION_ENV, "EVOLUTION_INSTANCE_NAME": value}))


def test_a_blank_api_key_is_rejected() -> None:
    """I5: an empty credential is an unset credential wearing a disguise."""
    with pytest.raises(ConfigError, match="EVOLUTION_API_KEY"):
        load_config(env_with(**{**EVOLUTION_ENV, "EVOLUTION_API_KEY": "   "}))


def test_the_api_key_is_named_but_never_repeated_in_the_error() -> None:
    """I5: the error text reaches the logs, and the gateway credential must not ride along."""
    broken = env_with(
        **{
            **EVOLUTION_ENV,
            "EVOLUTION_BASE_URL": "not-a-url",
            "EVOLUTION_API_KEY": "placeholder-that-must-not-be-echoed",
        }
    )

    with pytest.raises(ConfigError) as raised:
        load_config(broken)

    assert "EVOLUTION_BASE_URL" in str(raised.value)
    assert "placeholder-that-must-not-be-echoed" not in str(raised.value)


def test_the_gateway_configuration_is_reachable_through_django_settings() -> None:
    """B26: one boundary loads it, and the adapter of B8 reads it from there."""
    gateway = EvolutionConfig(
        base_url="http://evolution:8080",
        instance_name="valeverde",
        api_key="placeholder-value-for-tests-only",
    )

    with override_settings(EVOLUTION=gateway):
        assert get_evolution_config() == gateway


def test_an_unconfigured_gateway_reads_as_none_rather_than_as_an_error() -> None:
    """B26: phase one has no gateway, and asking for one there is answered, not punished; the
    loud refusal belongs to the provider the daily run resolves (B8)."""
    with override_settings(EVOLUTION=None):
        assert get_evolution_config() is None


def test_every_problem_in_an_environment_is_reported_at_once() -> None:
    """B2: filling in a .env is not a game of whack-a-mole."""
    broken = env_with(
        DEADLINER_SEND_TIME="seven",
        DEADLINER_WHATSAPP_DESTINATION="not-a-destination",
        DEADLINER_TIMEZONE="Mars/Olympus_Mons",
    )

    with pytest.raises(ConfigError) as raised:
        load_config(broken)

    assert "DEADLINER_SEND_TIME" in str(raised.value)
    assert "DEADLINER_WHATSAPP_DESTINATION" in str(raised.value)
    assert "DEADLINER_TIMEZONE" in str(raised.value)


def test_a_rejected_secret_is_named_but_never_repeated_in_the_error() -> None:
    """I7: the error text reaches the logs, and the secret must not ride along."""
    with pytest.raises(ConfigError) as raised:
        load_config(env_with(DEADLINER_SECRET_PATH_SEGMENT="leaked/with/slashes"))

    assert "DEADLINER_SECRET_PATH_SEGMENT" in str(raised.value)
    assert "leaked/with/slashes" not in str(raised.value)


def test_the_business_configuration_is_reachable_through_django_settings() -> None:
    """I4: one boundary loads it, and every caller reads it from there."""
    assert isinstance(get_config(), DeadlinerConfig)


def test_a_missing_business_configuration_is_an_error_and_never_a_none() -> None:
    """B2: a caller never receives a half-configured application."""
    with override_settings(DEADLINER=None), pytest.raises(ConfigError):
        get_config()


def test_django_renders_dates_in_the_configured_timezone() -> None:
    """B2: one timezone value, not a second literal in the settings module."""
    assert os.environ["DEADLINER_TIMEZONE"] == settings.TIME_ZONE


def test_the_tracked_example_environment_is_a_working_configuration() -> None:
    """I5: the real .env is untracked, so .env.example is what a new machine copies."""
    example = parse_env_file(REPOSITORY_ROOT / ".env.example")

    assert isinstance(load_config(example), Config)
