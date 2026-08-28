# Dependencies

Derives from `specs/foundation.md` section 8 and loses to it. This file records what was pinned, from
which source, on which date, and what was learned while confirming it. The standing rule in
`CLAUDE.md` sends every library finding here, never to a code comment. Pins live in
`requirements.txt` (runtime) and `requirements-dev.txt` (development and CI); this file explains them.

## Toolchain (confirmed 2026-08-28)

| Tool | Version | Source consulted | Note |
| --- | --- | --- | --- |
| Python | 3.13.3 | local interpreter, `venv/` | Django 5.2 supports 3.10 to 3.13 (3.14 from 5.2.8), per the 5.2 install FAQ |
| pip + venv | pip 25.0.1 | standard library | Owner decision of 2026-08-28: plain venv, no uv (foundation section 13) |
| just | 1.58.0 | winget `Casey.Just` | Recipes call `venv/Scripts/python.exe` on Windows and `venv/bin/python` elsewhere |
| Docker | 28.5.1 | local | Compose file is `compose.yaml`; base image `python:3.13-slim` |
| jq | 1.8.2 | winget `jqlang.jq` | Required by the hooks in `.claude/hooks/`; it was missing on the owner's machine until 2026-08-28 |

## Runtime pins (`requirements.txt`)

| Package | Pin | Source consulted | Finding |
| --- | --- | --- | --- |
| django | 5.2.17 | djangoproject.com/download, PyPI JSON | 5.2 is the current LTS: mainstream support ended 2025-12-03, extended support to April 2028. 6.1 is the latest non-LTS. The pre-existing scaffold on disk had been generated with 6.0.7 and was regenerated with the 5.2 CLI on 2026-08-28. Upper bound `<5.3` is intentional: the LTS line is the decision. |
| gunicorn | 26.2.0 | PyPI JSON, Django 5.2 gunicorn how-to | Django's how-to gives `gunicorn myproject.wsgi`, run from the directory holding `manage.py`; the Dockerfile uses `gunicorn deadliner.wsgi --bind 0.0.0.0:8000`. Chosen as the WSGI server because `runserver` is development-only; not a foundation decision, so it is recorded here and can be swapped without a revision. |

## Development pins (`requirements-dev.txt`)

| Package | Pin | Source consulted | Finding |
| --- | --- | --- | --- |
| django-stubs[compatible-mypy] | 6.1.0 | typeddjango/django-stubs README | Supports Django 6.1, 6.0 and 5.2 with mypy 1.13 to 2.3; the `compatible-mypy` extra installs a matching mypy (resolved 2.3.1 on 2026-08-28). Configured through `[tool.mypy] plugins` and `[tool.django-stubs] django_settings_module` in `pyproject.toml`. The plugin imports the settings module, so mypy needs the Django env vars; `just` loads `.env` and CI sets them. |
| pytest | 9.1.1 | docs.pytest.org customize page | Native `[tool.pytest]` table in `pyproject.toml` is supported since 9.0 and is what we use. |
| pytest-django | 4.14.0 | pytest-django configuring page | Reads `DJANGO_SETTINGS_MODULE` from `[tool.pytest]`; `--ds` and the env var take precedence over it. |
| ruff | 0.16.5 | docs.astral.sh/ruff configuration | `ruff check` and `ruff format --check` are the two gate commands; rules selected: E, F, I, B, UP, SIM, DJ, RUF; line length 100. `core/migrations` and `venv` are excluded. |

## CI and secret scan

| Piece | Version | Source consulted | Finding |
| --- | --- | --- | --- |
| actions/checkout | v7 | GitHub releases API (v7.0.1) | `fetch-depth: 0` so the secret scan sees the whole history. |
| actions/setup-python | v7 | GitHub releases API (v7.0.0) | `cache: pip` keyed on the requirements files. |
| gitleaks-action | v3 | gitleaks/gitleaks-action README | Needs only `GITHUB_TOKEN` on a personal account; an organisation repository needs a `GITLEAKS_LICENSE` secret (free at gitleaks.io). Reads `.gitleaks.toml` at the repository root. |
| gitleaks (local) | v8.30.1 | GitHub releases API, gitleaks README | `just secret-scan` runs `ghcr.io/gitleaks/gitleaks` in `dir` mode over the working tree, so uncommitted files are scanned before they are staged; `.gitleaks.toml` extends the default rules and allowlists the untracked `.env` and the virtualenv folders. |

## Evolution API (B8 spike, OQ-1 still open)

Confirmed 2026-08-28 from the official repository (`EvolutionAPI/evolution-api`, now under the
Evolution Foundation), its `docker-compose.yaml` and `.env.example`, the GitHub releases API, the
Docker Hub tags API, and the source at git tag `2.3.7`. The documentation site moved from
`doc.evolution-api.com` to `docs.evolutionfoundation.com.br`.

| Piece | Pin | Source consulted | Finding |
| --- | --- | --- | --- |
| evolution-api image | `evoapicloud/evolution-api:v2.3.7` | Docker Hub tags, GitHub releases | 2.3.7 (2025-12-05) is the latest stable release; 2.4.0 exists only as release candidates (rc1 2026-05-06, rc2 2026-05-17) and the `latest` tag points at an rc, so `latest` is never used. The old `atendai/evolution-api` image stopped at v2.2.3 (2025-02). Git tags carry no `v` prefix (`2.3.7`), Docker tags do (`v2.3.7`). The image is Node 24 on Alpine, port 8080. |
| PostgreSQL | `postgres:15` | official `docker-compose.yaml` | The vendor's own compose uses 15. Owned by the Evolution service: database `evolution`, user `evolution`, password `EVOLUTION_DB_PASSWORD`, volume `evolution_postgres`. |
| Redis | `redis:7-alpine` | official `docker-compose.yaml` (uses `redis:latest`) | Pinned to a major instead of `latest`; `appendonly yes` as in the vendor file, volume `evolution_redis`. |
| Environment | see `compose.yaml` | official `.env.example`, env reference page | Set in `compose.yaml` under the `evolution` service, only the secrets come from `.env`: `EVOLUTION_API_KEY` (becomes `AUTHENTICATION_API_KEY`, the `apikey` header of every call) and `EVOLUTION_DB_PASSWORD`. `EVOLUTION_SERVER_URL` defaults to `http://localhost:8080`. Telemetry off, `DEL_INSTANCE=false` so a disconnected instance is kept, `LANGUAGE=pt-BR`, `CONFIG_SESSION_PHONE_CLIENT` is the name shown on the phone. Sessions persist in the `evolution_instances` volume. |
| Endpoints | git tag `2.3.7` | `src/api/dto/sendMessage.dto.ts`, `src/validate/message.schema.ts`, `src/api/routes/sendMessage.router.ts`, doc pages for instance create, connect and connectionState | `POST /instance/create` body `{instanceName, integration: "WHATSAPP-BAILEYS", qrcode: true}`; `GET /instance/connect/{name}` returns `base64` (PNG data URI) and `pairingCode`; `GET /instance/connectionState/{name}` returns `instance.state` in `open`, `close`, `connecting`; `POST /message/sendText/{name}` body `{number, text}` with optional `delay`, `linkPreview`, and the response carries `key.id` and `status`. Trap: the send-text documentation page still shows the v1 body (`textMessage.text`); the 2.3.7 source is the authority and takes top-level `text`. |

Exit criterion of OQ-1 (one real message delivered to the company number) is not yet met. Done on
2026-08-28, verified on the owner's machine: `just evolution-up` boots the three services, the
Prisma migrations run at container start, `GET /` answers `version 2.3.7` and names the manager UI
at `http://localhost:8080/manager` (login with the API key), `POST /instance/create` created
`valeverde` in state `connecting`, and `GET /instance/connect/valeverde` returned a QR code that
`just evolution-qr` saved as a PNG. Not done: pairing the phone (a human scans the QR, which
rotates every few seconds up to `QRCODE_LIMIT`, so generate it right before scanning) and the send.

Trap met on the way: after the disk-full incident the locally cached image had zero-byte files
(`dist/main.js`, `Docker/scripts/*.sh`), so the container exited 0 in silence and restarted in a
loop. `docker image rm` and a fresh `docker compose pull` fixed it; the integrity check is
`docker run --rm --entrypoint sh evoapicloud/evolution-api:v2.3.7 -c 'ls -la dist/main.js'`.

## Runtime environment, confirmed during B2 (2026-08-28)

Confirmed by running each check against the pinned versions, never from memory. No new package was
added; every finding here is about behaviour that shaped `deadliner/config.py`.

| Piece | Finding |
| --- | --- |
| `zoneinfo` in `python:3.13-slim` | The image already carries the IANA database, 486 zones, and `America/Campo_Grande` resolves inside it. No `tzdata` package is needed in `requirements.txt`. |
| `zoneinfo.ZoneInfo` failures | An unknown name raises `ZoneInfoNotFoundError`, a subclass of `KeyError`, but a name that is not a normalized relative path raises `ValueError`. Validation catches both; catching only `KeyError` lets `../../etc/passwd` reach a different failure. |
| `string.Formatter().parse` | Malformed braces raise `ValueError` while the result is iterated. `{}` yields the field name `''`, `{0}` yields `'0'`, `{a.b}` and `{a[0]}` yield the whole expression, and a format spec or conversion is stripped. Membership against an allowed set therefore rejects positional and attribute access for free. |
| dotenv parsing | The parser behind `just` rejects an unquoted value containing spaces, so the message template is quoted in `.env.example`. Both `just` and Docker Compose `env_file` strip the surrounding quotes, checked by printing the loaded value through each. |
| gitleaks `generic-api-key` | Fires on an alphanumeric string of sixteen or more characters near the word secret, which any test of the secret path segment trips by nature. Fixtures use obviously fake low entropy values; an allowlist over the test tree would blind the C5 gate exactly where a real credential could be pasted. |
| `just setup` on Linux | The recipe builds the virtualenv from whatever `python` is on PATH. On Fedora 44 that is 3.14, while the canon, the Dockerfile and CI are all 3.13, so the local venv was created with `python3.13` by hand. Fixed in the review window of 2026-08-28: the recipe now calls `py -3.13` on Windows and `python3.13` elsewhere. |

## Runtime environment, confirmed during B4 (2026-08-28)

| Piece | Finding |
| --- | --- |
| `forms.ModelForm[Service]` | Generic only in django-stubs; the runtime class is not subscriptable (`TypeError`). `core/forms.py` aliases it under `TYPE_CHECKING`, which keeps `mypy --strict` satisfied without `django_stubs_ext.monkeypatch()`, a development-only package that must not be imported by production code. |
| Date input under `pt-br` | `django.utils.formats.get_format` appends the ISO formats to the locale list, so a `DateField` accepts `2026-12-25` (what an HTML date input posts) as well as `25/12/2026`. Verified in the pinned 5.2.17 source. |
| Django's own messages in Portuguese | With `LANGUAGE_CODE = "pt-br"` the required-field error is `Este campo é obrigatório.` and the bad-date error `Informe uma data válida.`, from the pinned `pt_BR` catalogue. |
| Choice labels and migrations | Changing a `TextChoices` label alters the field's `choices`, so the CLI generates a migration (`0002_alter_service_status`); labels are therefore a schema-level change in this project, not a template one. |

## Runtime environment, confirmed during B5 (2026-08-28)

Confirmed by reading the pinned sources and the installed package, never from memory. No new
package was added.

| Piece | Finding |
| --- | --- |
| gunicorn access log | `accesslog` defaults to `None` in the pinned 26.2.0, so the container writes no access line and the secret path segment cannot leak that way today. The error log defaults to stderr. Gunicorn does not read Django's `LOGGING`, so passing `--access-logfile` would write the full request path past the redaction filter of I7. B11 owns that trap on the production host. |
| Django logging configuration | `django.utils.log.configure_logging` in 5.2.17 runs `dictConfig(DEFAULT_LOGGING)` first and the project's `LOGGING` second. `DEFAULT_LOGGING` gives the `django` logger a console handler that this project does not filter, so `LOGGING` redefines that logger. Its `django.server` logger is a child of `django`, and `logging.config` resets the children of a reconfigured logger, so the runserver request line propagates into the filtered handler with no entry of its own. |
| `logging.Filter` placement | A filter on a logger runs only for records created by that exact logger, never for records propagated from a child, so redaction lives on the handler where every record passes. Mutating `record.msg` requires clearing `record.args`, or the handler interpolates a second time against a string that no longer carries the placeholders. |
| Compose healthcheck | `python:3.13-slim` carries no curl or wget, so the healthcheck probes the endpoint with `python -c` and `urllib.request`. It requests the loopback address, which `DJANGO_ALLOWED_HOSTS` must therefore list or Django answers 400 and the container reads as unhealthy. |

## Runtime environment, confirmed during B6 (2026-08-28)

Confirmed against Cloudflare's own documentation and the pinned Django source, never from memory.
No new package was added: the structured formatter is the standard library.

| Piece | Finding |
| --- | --- |
| Cloudflare forwarding headers | `CF-Connecting-IP` carries the visitor address (`True-Client-IP` is the Enterprise alias). `CF-IPCountry` carries a two letter ISO 3166-1 code, plus `XX` for a client with no country data and `T1` for the Tor network, and it is added only when the "Add visitor location headers" Managed Transform is enabled on the zone. I6 is therefore untestable in production until that transform is on, which belongs to OQ-2. Source: Cloudflare fundamentals, HTTP request headers. |
| Django logs a 4xx outside the middleware chain | `BaseHandler.get_response` in 5.2.17 calls `log_response` after `self._middleware_chain(request)` returns, so a middleware that binds a correlation key and resets it on the way out has already reset it when the framework writes `Not Found`. The correlated line about a request is the one the application writes itself, before the reset. |
| `django.request` records carry the request object | `log_response` passes `extra={"status_code": ..., "request": request}`. A structured formatter renders that object through `str()`, which prints the full path, so redaction has to check values in the form they will be written and not only strings (I7). |
| `contextvars` under the sync stack | The binding survives across the middleware chain and the view in the same thread, and a reset in `finally` keeps a line written after the response from carrying a stale address. Gunicorn sync workers handle one request at a time per worker, so no cross request bleed exists to defend against beyond that reset. |

## Log

2026-08-28: B6 added the runtime environment section above; no pin changed and no package was
added.

2026-08-28: B5 added the runtime environment section above; no pin changed and no package was
added.

2026-08-28: B4 added the runtime environment section above; no pin changed.

2026-08-28: Evolution API section added by the B8 spike; OQ-1 stays open until a real message lands.

2026-08-28: file created with the B1 pins. Owner replaced uv with venv and pip during B1; the earlier
uv lock was deleted, nothing had been committed with it.

2026-08-28: B2 added the runtime environment section above. No pin changed and no package was added.
