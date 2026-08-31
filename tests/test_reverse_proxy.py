"""B11, the deployment sits behind a reverse proxy that terminates TLS.

Trace: foundation section 8 (Cloudflare fronts the public hostname, and until that zone moves the
host's own nginx does), section 6 (the administration site keeps Django's authentication, so its
session cookie crosses that hop). The defect these tests exist against is specific and total:
Django decides whether a request is secure from the connection it sees, which is plain HTTP from
the proxy, so unless the hop is declared it builds the expected CSRF origin as `http://host` while
the browser sends `https://host`, they do not match, and every POST in the application is refused.
"""

import pytest
from django.test import Client, override_settings
from django.urls import reverse

import deadliner.settings as settings_module
from tests.builders import a_catalog_service, a_submitter, registration_payload

pytestmark = pytest.mark.django_db

HOST = "avisos.example.com.br"

# What nginx puts on the request: the name the browser asked for, and the protocol it spoke to the
# proxy, which is the only evidence Django has that the hop was encrypted.
FORWARDED = {"host": HOST, "x-forwarded-proto": "https"}


def _client_holding_a_token() -> tuple[Client, str]:
    """A client that has visited the form over the proxy, and the token it was given."""
    client = Client(enforce_csrf_checks=True)
    client.get(reverse("service-create"), headers=FORWARDED)
    return client, client.cookies["csrftoken"].value


def _post(client: Client, token: str, origin: str) -> int:
    service = a_catalog_service()
    a_submitter("José Victor")
    payload = registration_payload(catalog_service=str(service.pk), csrfmiddlewaretoken=token)
    response = client.post(
        reverse("service-create"), payload, headers={**FORWARDED, "origin": origin}
    )
    return response.status_code


def test_the_forwarded_protocol_header_is_what_decides_a_request_is_secure() -> None:
    """B11: TLS ends at the proxy, so the hop is declared or no request is ever secure."""
    assert settings_module.SECURE_PROXY_SSL_HEADER == ("HTTP_X_FORWARDED_PROTO", "https")


@override_settings(ALLOWED_HOSTS=[HOST])
def test_a_form_posted_over_the_proxy_is_accepted() -> None:
    """B11: the browser sends an https origin and Django has to agree that it is one.

    Without the forwarded protocol setting this is a 403 and every screen in the application
    stops working the moment anything but Django itself terminates the TLS.
    """
    client, token = _client_holding_a_token()

    assert _post(client, token, f"https://{HOST}") == 302


@override_settings(ALLOWED_HOSTS=[HOST])
def test_a_form_posted_from_a_foreign_origin_is_still_refused() -> None:
    """B11: declaring the hop tells the origin check the truth, it never turns the check off."""
    client, token = _client_holding_a_token()

    assert _post(client, token, "https://outro-site.example.com") == 403


def test_the_session_and_csrf_cookies_are_https_only_outside_debug() -> None:
    """B11: the administration site sends a password over that hop (foundation section 6).

    Read from the settings module and not from `django.conf.settings`, because the test runner
    forces `DEBUG` false on the latter whatever the environment said, which would make this
    assertion pass or fail on where it ran rather than on the rule it is about.
    """
    assert settings_module.SESSION_COOKIE_SECURE is not settings_module.DEBUG
    assert settings_module.CSRF_COOKIE_SECURE is not settings_module.DEBUG
