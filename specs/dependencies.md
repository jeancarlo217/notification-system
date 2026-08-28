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

## Log

2026-08-28: file created with the B1 pins. Owner replaced uv with venv and pip during B1; the earlier
uv lock was deleted, nothing had been committed with it.
