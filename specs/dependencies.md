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
| `just setup` on Linux | The recipe builds the virtualenv from whatever `python` is on PATH. On Fedora 44 that is 3.14, while the canon, the Dockerfile and CI are all 3.13, so the local venv was created with `python3.13` by hand. The recipe is still unfixed. |

## Log

2026-08-28: file created with the B1 pins. Owner replaced uv with venv and pip during B1; the earlier
uv lock was deleted, nothing had been committed with it.

2026-08-28: B2 added the runtime environment section above. No pin changed and no package was added.
