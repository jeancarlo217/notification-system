"""B1, repository and scaffold: the generated project is a valid Django configuration."""

from django.core.management import call_command


def test_django_system_checks_pass() -> None:
    """B1: the settings module loads and Django's system checks report no issue."""
    call_command("check")
