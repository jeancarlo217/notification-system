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
| whitenoise | 6.12.0 | PyPI JSON, whitenoise.readthedocs.io Django integration page and changelog | Latest release (2026-02-27), zero required dependencies. Django 5.2 has been supported since 6.9.0 and Python 3.13 since 6.10.0; the 6.12.0 classifiers name Django 4.2 to 6.0 and Python 3.10 to 3.14, `requires_python >=3.10`. Added because nothing under a static directory was served in the Compose stack before B16, which left the administration site of foundation section 6 unstyled in the deployment target. 6.12.0 also fixes an unauthorised file access issue in autorefresh mode; autorefresh follows `DEBUG`, so it is off in the deployment configuration. |

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

## Static files, confirmed during B16 (2026-08-28)

Confirmed against the WhiteNoise documentation, the installed 6.12.0 source, the pinned Django
5.2.17 source and the running container, never from memory. One package was added.

| Piece | Finding |
| --- | --- |
| Middleware position | The Django integration page requires `WhiteNoiseMiddleware` directly after `SecurityMiddleware` and before every other middleware. This project keeps `RequestContextMiddleware` first so a static response still carries its correlation keys (foundation section 8), and WhiteNoise sits second, ahead of session, common, CSRF and authentication. |
| Serving prefix | `WhiteNoiseMiddleware.__init__` in 6.12.0 takes `static_prefix` from `urlparse(settings.STATIC_URL).path`, so `STATIC_URL` alone decides what it answers on. Django's `Settings._add_script_prefix` turns a value with no leading slash into an absolute one at settings load, which is why the old `"static/"` worked. |
| Static lives inside the secret path segment | Foundation section 6 says the health endpoint is the single route outside the segment, so `STATIC_URL` is built from `secret_path_segment` and every asset answers at `/<segment>/static/...`. Verified in the container: that prefix returns 200 and a bare `/static/admin/css/base.css` returns 404. The administration site follows automatically, because its templates use the `static` tag. |
| Storage backend | `whitenoise.storage.CompressedStaticFilesStorage`, not the manifest variant. `CompressedManifestStaticFilesStorage` inherits Django's `ManifestFilesMixin`, whose `manifest_strict` defaults to `True`, and whose `stored_name` raises `ValueError: Missing staticfiles manifest entry` whenever the manifest is absent. With no manifest on disk every `{% static %}` in the suite would raise, so manifest storage makes `just test` depend on a `collectstatic` having run. The loud-build-failure argument does not survive the mechanism either: a bad reference in a template fails at render time as a 500, not at build time, because `collectstatic` only rewrites references found inside collected CSS and JS. The asset set is four brand files plus the administration bundle, served to a handful of employees on one hostname, so hashed names and far future caching buy nothing here. Compression is kept: `collectstatic` wrote 131 files and a `.gz` beside each compressible one. |
| `STORAGES` is replaced, never merged | `django.core.files.storage.handler` copies `settings.STORAGES` as given and raises `InvalidStorageError` for a missing alias, so the settings module declares `default` as well as `staticfiles`. |
| `collectstatic` at image build | The configuration boundary validates the whole environment on import, and a `docker build` has no `.env`, so the `collectstatic` line in the Dockerfile passes obviously fake values for the seven required variables. Nothing it writes carries a URL, so the placeholder segment never reaches the collected tree; the runtime environment is what `STATIC_URL` is built from. |
| Defaults keyed on `DEBUG` | In 6.12.0 `autorefresh`, `use_finders` and `max_age` all fall back to `settings.DEBUG`: with `DEBUG=1` the container answered `Cache-Control: max-age=0, public` and served no compressed variant, because it was reading through the finders. With `DEBUG=0`, the deployment configuration, it answered `max-age=60, public`, `Vary: Accept-Encoding` and `Content-Encoding: gzip`, and `admin/css/base.css` went from 22120 to 4950 bytes. Any acceptance check of the static pipeline has to run with `DEBUG=0` or it measures the wrong code path. |
| Missing `STATIC_ROOT` warns per request | WhiteNoise emits `UserWarning: No directory at: .../staticfiles/` when `STATIC_ROOT` does not exist, once per middleware construction, so the suite prints one per test client. The directory is a build artifact that only `collectstatic` creates, and the warning is accurate rather than noise to suppress. It disappears once `collectstatic` runs; see the open follow-ups below. |

### Contrast measured for B16 (WCAG 2.1 relative luminance, computed, not estimated)

The brand hexes are `#72BF00` and `#00312D`. They are anchored on the solid accent and nowhere
that carries reading text, because `#72BF00` is too light to carry text or a hairline on a light
page. Text needs 4.5:1, and a focus ring or a control boundary needs 3:1.

| Pair | Light | Dark |
| --- | --- | --- |
| Primary button text, `--brand-ink` on `--brand-green` | 6.21:1 | 6.21:1 |
| Primary button text on hover, `--brand-ink` on `#66ab00` | 5.00:1 | 5.00:1 |
| Primary button fill against the page | 2.17:1 | 7.71:1 |
| Focus ring, green 11, against canvas and panel | 4.46:1 and 4.62:1 | 10.03:1 and 9.42:1 |
| Focus ring B14 used, green 8, against canvas and panel | 2.27:1 and 2.35:1 | 3.71:1 and 3.48:1 |
| Control boundary, sage 9, against panel and canvas | 3.29:1 and 3.17:1 | 3.42:1 and 3.64:1 |
| Control boundary B14 used, sage 7, against panel | 1.54:1 | 1.93:1 |
| Badge text, green 12 on green 3 | 11.00:1 | 11.45:1 |
| Badge text B14 used, green 11 on green 3 | 4.21:1 | 7.86:1 |
| Link and accent text, green 11, on canvas | 4.46:1 | 10.03:1 |
| Error text, red 11, on the error panel red 3 | 4.54:1 | 7.75:1 |
| Placeholder, sage 10, on panel | 3.76:1 | 4.13:1 |
| Body text, sage 12, on canvas | 15.51:1 | 16.14:1 |

Three of these were failures B14 shipped and B16 repairs: the focus ring at 2.27:1 where a ring
needs 3:1, the form control boundary at 1.54:1 where a control boundary needs 3:1, and the badge
text at 4.21:1 where text needs 4.5:1. White on the brand green measures 2.29:1 and was rejected;
the brand ink on it measures 6.21:1 and is what the primary button uses. The button fill itself
carries only 2.17:1 against a light page, so the boundary that identifies the button is an ink
border rather than the green.

### Browser findings

| Piece | Finding |
| --- | --- |
| Theme in three states | A media query cannot be reopened by an attribute rule, so the dark palette is declared twice, once under `@media (prefers-color-scheme: dark)` scoped to `:root:not([data-theme="light"])` and once under `:root[data-theme="dark"]`. `test_the_two_dark_theme_blocks_declare_the_same_tokens` compares the two, because a value edited in one of them is a defect visible in exactly one of the three states. `color-scheme: light dark` on `:root` makes the browser resolve scrollbars, the date picker and form controls from the operating system with no script, and the two attribute rules force one value when a person overrides it. |
| `light-dark()` was rejected | It would remove the duplication, but a custom property carries no parse time fallback: an unsupported browser leaves every token invalid at computed value time and the page loses its colours. Baseline since 2024 is too recent to bet an internal tool on. |
| The lockup swap | A `picture` element with a `prefers-color-scheme` source follows the operating system and ignores a manual override, so the two lockups are two `img` elements swapped by the same selectors that swap the tokens. Both carry `alt="Vale Verde Ambiental"`: the word mark is the only place the company is named on screen, and the hidden one is `display: none`, so it leaves the accessibility tree and never announces twice. |
| `display: flex` on a `td` | B14 gave `.table__actions` `display: flex`. That takes the cell out of the table box tree, the browser wraps it in an anonymous table cell, and the result paints a lighter band with a visible vertical seam down the whole actions column at every width above the phone layout. Confirmed by removing the declaration and re-screenshotting the same page. The buttons are laid out inline instead, and the phone layout keeps flex because there the cells are already blocks. |
| Headless verification | Google Chrome 152.0.7977.64, `--headless=new`, at 360, 768 and 1280 CSS pixels. It reads the desktop colour scheme: `matchMedia("(prefers-color-scheme: dark)")` reported true on this machine, so the light theme could only be reached through the manual override, which is the case worth checking. The stored choice was seeded through a page served from the same origin so the real script and the real `localStorage` ran, rather than by editing the attribute by hand. |
| Date input format | Chrome renders `input type="date"` in the browser UI locale, not the document `lang`, so the headless screenshots showed `mm/dd/yyyy` on a Portuguese page. **Corrected on 2026-08-31 by B23**: the sentence that once closed this row, "not something the page can set", was true of that widget and false of the page. A page that stops using the native widget decides its own order. The consequence of leaving it was not cosmetic, which is why B23 replaced it: an employee shown `mm/dd/yyyy` types the day first and the browser reads it as the month, so the record is stored months away with no error anywhere. |
| Date parsing under pt-BR | Confirmed on 2026-08-31 against the project's own settings, not from memory: `DATE_INPUT_FORMATS` resolves to `['%d/%m/%Y', '%d/%m/%y', '%Y-%m-%d']`, so `05/09/2026` parses as the fifth of September and the ISO form still parses. The server side was never the defect; only the widget was. |

## Responsive layout, measured during B21 (2026-08-31)

Google Chrome 152.0.7977.64, `--headless=new`, `--force-device-scale-factor=1`, against the
Compose stack, at 360, 414, 768, 1024, 1088, 1120, 1280 and 1440 CSS pixels. Measured rather than
reasoned about, which is the whole point of the item: B15 shipped its layout on reasoning and the
suite alone and the suite cannot see a column that is off screen.

| Piece | Finding |
| --- | --- |
| Where seven columns actually fit | The table needs about 1020 pixels of content with the cell padding at `--space-3`, and `.shell` caps at 66rem with 32 pixels of padding each side, so the window has to be past roughly 1082 pixels before the table has the room. The switch is set at 68rem. Above it the whole table fits with both action buttons; at 1024, where B15 left a table, the actions column was off screen. |
| Cell padding | Dropping the horizontal cell padding from `--space-4` to `--space-3` takes about 56 pixels off the table's content width across seven columns, which is the difference between fitting inside the 66rem shell and being clipped by the card. |
| `width: 1%` and a flex row | The table layout algorithm reads `width: 1%` as "shrink to content", and the content minimum of a wrapping flex row is its widest item, so three warning chips stacked into three lines in every row. `flex-wrap: nowrap` inside the cell makes the minimum the whole row; the card layout restores wrapping, where the width is the card and not the column. |
| `::before` specificity | `.table td::before` is one class and one type, `.table__client::before` is one class, so a `content: none` written against the class loses and the data label keeps printing. Every suppression has to be written `.table td.table__client::before`. |
| Cards two to a row | `grid-template-columns: repeat(auto-fill, minmax(21rem, 1fr))` on `tbody` gives one card per row on a phone and two from about 700 pixels, with no width named for the tablet case. |
| Actions inside a card | A wrapping flex row decides from the length of the button label, which is a Portuguese string nobody should be laying out around. `repeat(auto-fit, minmax(8rem, 1fr))` decides from the card width instead: the two buttons sit side by side wherever two fit and stack once they do not. |
| Contrast | No new pair. The chips reuse the four pairs B15 measured and B16 recorded: green 12 on green 3, red 11 on red 3, sage 12 on sage 3, and sage 11 on the panel. The mark is drawn in `currentColor`, so it carries the contrast of the text beside it. |

## Backups, confirmed during B22 (2026-08-31)

Confirmed against the CPython 3.13 `sqlite3` documentation, `https://www.sqlite.org/backup.html`
for the C level guarantee, and the installed interpreter (Python 3.13.15, `sqlite3.sqlite_version`
3.51.2), then measured rather than trusted. No package was added.

| Piece | Finding |
| --- | --- |
| `Connection.backup()` signature | `backup(target, *, pages=-1, progress=None, name='main', sleep=0.250)`, and `inspect.signature` on the installed build returns exactly that, so the pinned interpreter matches the documented one. |
| Why it is used instead of copying the file | `pages` at or below zero copies the whole database in one step, and SQLite's own page explains what that buys: a single `sqlite3_backup_step` holds a read lock on the source for the duration, so the result is a consistent snapshot. A `cp` of a live database can copy a file mid transaction and produce something that does not open, which is discovered on the day it is needed. |
| Concurrent writers | Documented to work while other clients are accessing the database, and measured: with a second connection holding an open `INSERT`, the copy succeeded, `pragma integrity_check` returned `ok`, and the copy carried the committed row and not the uncommitted one. Bit-wise identity is documented but does not hold in that scenario, so nothing asserts it. |
| **It hangs on a self locked source** | The documentation's "concurrently by the same connection" does not extend to a source connection holding an open write transaction. There `sqlite3_backup_step` answers `SQLITE_LOCKED` forever and CPython retries inside a C loop that no Python signal handler reaches: a `SIGALRM` set at five seconds never fired and the process had to be `SIGKILL`ed. A hanging daily job is a silent failure, so the code refuses that state and raises. The command tests therefore need `transaction=True` and `serialized_rollback=True`, because plain `django_db` wraps each test in an atomic block. |
| `.dockerignore` matching | A pattern matches one path segment, so the pre-existing `*.sqlite3` excluded a database at the root and not `backups/db-*.sqlite3`. Measured: the built image carried two 192 KB copies under `/app/backups`, and after adding `**/*.sqlite3`, `**/*.sqlite` and `backups` the directory is absent from the image. Production data in a distributable image is I5. |
| Time zone of the copy name | The file is named in the configured zone and not the host's, verified during the drill: the host clock read 13:56 at UTC-3 while the copy was written `12-56-44`, which is America/Campo_Grande at UTC-4. |

## Log

2026-08-31: B22 added the backups section above; no pin changed and no package was added.

2026-08-31: B21 added the responsive layout section above; no pin changed and no package was added.

2026-08-28: B16 added whitenoise 6.12.0, the first runtime pin since B1, and the static files section above. Static is served inside the secret path segment.

2026-08-28: B6 added the runtime environment section above; no pin changed and no package was
added.

2026-08-28: B5 added the runtime environment section above; no pin changed and no package was
added.

2026-08-28: B4 added the runtime environment section above; no pin changed.

2026-08-28: Evolution API section added by the B8 spike; OQ-1 stays open until a real message lands.

2026-08-28: file created with the B1 pins. Owner replaced uv with venv and pip during B1; the earlier
uv lock was deleted, nothing had been committed with it.

2026-08-28: B2 added the runtime environment section above. No pin changed and no package was added.
