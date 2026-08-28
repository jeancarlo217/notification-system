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
2026-08-28: the Compose services, the keys in `.env.example`, the `just evolution-*` recipes, and
`docker compose config` validates. Not done: booting the stack on the owner's machine (the disk had
0.2 GB free and Docker Desktop failed with an I/O error on its data disk), pairing the phone (a
human scans the QR), and the send. The `just` recipes carry the remaining steps in order.

## Log

2026-08-28: Evolution API section added by the B8 spike; OQ-1 stays open until a real message lands.

2026-08-28: file created with the B1 pins. Owner replaced uv with venv and pip during B1; the earlier
uv lock was deleted, nothing had been committed with it.
