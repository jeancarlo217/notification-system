# Deadline Notification System

An internal tool for Vale Verde Ambiental. A form records the services the company owes a client,
each with the date it starts and the term in days that gives it its deadline; every morning at
seven an engine sends one message listing every service still open, the nearest deadline first, to
a company WhatsApp group. Every submission is audited and no day's list is ever sent twice.

The canon lives in `specs/foundation.md`, which every other document derives from and loses to.
`CLAUDE.md` is the working digest. This file is only about running the thing.

## What you need

To **run** it: Docker with the Compose plugin. Nothing else.

To **develop** it: Python 3.13, [just](https://github.com/casey/just), and Docker for the secret
scan. Python 3.13 exactly, because the canon, the image and CI all pin it; 3.14 on your PATH will
build a virtualenv that disagrees with the one CI runs.

## Quick start

```bash
git clone https://github.com/jeancarlo217/notification-system.git
cd notification-system
cp .env.example .env
```

Now edit `.env`. Four values must change before anything will start, and the section below says
what each one is. Then:

```bash
docker compose up -d --build web
```

Open `http://localhost:8000/<your-secret-segment>/` in a browser. That is the whole application.

The first boot applies the migrations, which seed the fifteen catalogue services, ten of which the
company still offers, and the two known submitters, so the form is usable immediately.

### Why the URL has a segment in it, and why that segment is not a password

There is no login. The entire application is served under a path segment that lives in
configuration (foundation section 6). The one exception is `http://localhost:8000/health/`, which
the container runtime probes and which touches no dependency and reveals nothing.

So `http://localhost:8000/` answers 404 on purpose. It is not broken.

**Read this before deploying.** Until 2026-08-31 that segment was a credential: long, random, and
the only thing standing between the internet and every client deadline in the database. On
2026-08-31 the owner decided the link must be short enough to send to people in a message, and
that nothing replaces it: no login, no check at the edge, no list of allowed addresses. The
consequence, accepted in that decision and written here so nobody rediscovers it by accident, is
that **anyone who holds the link, is forwarded it, or guesses it can read every client and every
deadline, and can create, edit and complete records.** The audit trail records what happened and
from which address; it cannot say who did it, and it prevents nothing.

The two ways to have a short link and still have a door, both offered and both declined on
2026-08-31, are Cloudflare Access in front of the origin and an application login. Either can be
added later without touching the rest of the system.

If the segment ever needs changing, change `DEADLINER_SECRET_PATH_SEGMENT` and restart. Everybody's
bookmarks break.

## Configuration

Every value the application needs is an environment variable, validated at one boundary when the
process starts (`deadliner/config.py`, shape in `specs/adr/0001-configuration-boundary.md`). No
business value has a default in code, so a missing variable stops the process at boot with a
message naming it, rather than failing at three in the morning during a send.

`.env` is untracked and must stay that way. `.env.example` is the tracked template.

### The four you must set

| Variable | What it is |
| --- | --- |
| `DJANGO_SECRET_KEY` | Django's signing key. Any long random string. |
| `DEADLINER_SECRET_PATH_SEGMENT` | The URL segment above. At least 3 characters of `A-Za-z0-9_-`. It is not a password; read the section above before choosing it. |
| `DEADLINER_WHATSAPP_DESTINATION` | Where the warnings are delivered: the identifier of the company WhatsApp group, `<digits>@g.us`, or one number in digits only, country code first, no plus sign. The group identifier is read from Evolution and never typed from memory. **This variable was called `DEADLINER_WHATSAPP_NUMBER` until backlog B26; an existing `.env` has to be renamed or the process refuses to boot, naming it.** |
| `EVOLUTION_API_KEY` and `EVOLUTION_DB_PASSWORD` | Yours to invent. Compose refuses to parse the file without them even when you only start `web`. |

Generate the two random ones with:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"   # DJANGO_SECRET_KEY
```

`DEADLINER_SECRET_PATH_SEGMENT` is no longer generated: since 2026-08-31 it is a short word chosen
to be typed and sent, and the section above says what that costs.

`token_urlsafe` is the right generator here rather than Django's own `get_random_secret_key`,
whose alphabet includes punctuation that the dotenv parsers behind `just` and Compose read as
syntax.

### The rest

`DJANGO_DEBUG` (`0` or `1`, nothing else is accepted), `DJANGO_ALLOWED_HOSTS`,
`DJANGO_DATABASE_PATH`, `DJANGO_BACKUP_DIRECTORY` (where the daily database copies land, `backups`
by default and `/backups` inside the container), `DEADLINER_TIMEZONE` (`America/Campo_Grande`,
which decides what today means), `DEADLINER_SEND_TIME` (`07:00`, the hour the daily list is owed
from, written `HH:MM` and read in that time zone, never in the host's clock) and the seven values
the message is made of: `DEADLINER_MESSAGE_HEADER` (over the fields `count` and `date`),
`DEADLINER_MESSAGE_TEMPLATE` (one line of the list, over `client`, `service`, `due_date`,
`days_remaining` and `deadline`) and the five phrases one of which fills `deadline`,
`DEADLINER_DEADLINE_FUTURE`, `_TOMORROW`, `_TODAY`, `_YESTERDAY` and `_OVERDUE`, each over the
single field `days`. `.env.example` carries the wording the owner approved.

**`DEADLINER_ALERT_THRESHOLDS` no longer exists since backlog B27.** An existing `.env` may keep
the line, which is ignored, but it has to gain `DEADLINER_SEND_TIME`, `DEADLINER_MESSAGE_HEADER`
and the five `DEADLINER_DEADLINE_` phrases before the next deploy, or the process refuses to start
and names each one that is missing. Its `DEADLINER_MESSAGE_TEMPLATE` also has to become the line
in `.env.example`, since the placeholder it carried was one whole sentence per warning.

To read the message the group would receive, without sending anything:

```bash
docker compose exec web python manage.py send_alerts --preview
```

It calls no provider, writes nothing and ignores the send time, so it is safe at any hour and as
often as you like. It is also how the real message is read where the real records live, since
production data never leaves the production host.

The two path variables are infrastructure, not business values, so they are the only ones with a
default in code. Everything named `DEADLINER_` is required and refuses to boot without a value.

### The gateway the warnings go through

`EVOLUTION_BASE_URL` and `EVOLUTION_INSTANCE_NAME` name the Evolution instance the application
sends through, and `EVOLUTION_API_KEY` is what it presents there. The three are read at the same
boundary as everything else and are configured together or not at all: leaving both address
variables unset is phase one, which sends nothing and needs no gateway, and setting either one
without the API key is refused at startup rather than at send time. An `.env` that carries only
`EVOLUTION_API_KEY`, which Compose has demanded since the B8 spike, configures no gateway and
boots exactly as it did before.

The address is not the same string on both sides of the Docker network, and only one of them is
right per environment. Inside Compose the application reaches the gateway at
`http://evolution:8080`, the service name; `http://localhost:8080` is what the `just evolution-*`
recipes on the host call, and what `EVOLUTION_SERVER_URL` tells Evolution to advertise about
itself. Setting `EVOLUTION_BASE_URL` to `localhost` in a Compose deployment points the application
at its own container.

Keep `127.0.0.1` in `DJANGO_ALLOWED_HOSTS`. The Compose healthcheck probes the health endpoint on
the loopback address, and Django answers 400 to a host it does not allow, so dropping it makes a
perfectly healthy container report as unhealthy.

The message template contains spaces and therefore has to stay quoted in the file. Both `just` and
Compose strip the surrounding quotes.

## The administration site

Django's admin sits at `<segment>/admin/`, inside the secret path, with the framework's own
authentication. Two barriers guard it, the link and a password. It is the maintenance door for the
owner and the developers, never the employee facing product, and its accounts are not one per
employee.

Create the first account:

```bash
docker compose exec web python manage.py createsuperuser
```

That is where the service catalogue is edited. The fifteen services arrive by migration once and
are the company's responsibility from then on; adding, renaming or deactivating one is a form,
never a schema change. Deactivate, never delete: tracked deadlines point at those rows and the
foreign key will refuse. The five services under `Sustentabilidade e ESG` are deactivated in the
seed since 2026-08-31, because the company stopped performing them; anything already registered
against one still lists, still gets edited and still appears in the daily message.

## Running it

### With Docker, which is how it runs in production

```bash
docker compose up -d --build web     # the application alone, on port 8000
docker compose logs -f web           # follow its logs
docker compose ps                    # check health
docker compose down                  # stop, keeping the database
```

The SQLite file lives on a Docker volume mounted at `/data`, so `docker compose down` keeps your
data and only `docker compose down -v` destroys it.

`just up` starts everything instead: the web application, the scheduler, and Evolution API
with its own Postgres and Redis. You want that only when working on the WhatsApp integration.
Two warnings about the full stack. The scheduler polls `send_alerts` every minute and stays quiet
until the send time, and from then on it sends the day's list through whatever instance
`EVOLUTION_BASE_URL` names, so on a machine paired to the company account it messages the real
group. And Evolution pulls three more containers, so give it disk.

### Without Docker, for development

```bash
just setup     # virtualenv on Python 3.13, dependencies, .env from the example, collectstatic
just dev       # development server on port 8000
```

`just` loads `.env` for every recipe. This matters more than it looks: run `pytest` or `mypy`
directly and they will fail with five complaints about missing `DEADLINER_*` variables, which is
the configuration boundary working exactly as designed and looking exactly like a bug. Go through
`just`.

### Commands

`just` with no argument lists them all. The ones you will use:

| Command | What it does |
| --- | --- |
| `just dev` | Development server |
| `just manage <args>` | Any `manage.py` command |
| `just test [args]` | The test suite |
| `just lint` / `just format` | ruff, checking or applying |
| `just typecheck` | `mypy --strict` |
| `just secret-scan` | gitleaks over the working tree, needs Docker |
| `just gate` | All four, in the order CI runs them |
| `just up` / `just down` | The full Compose stack |
| `just backup` | One database copy now, into `./backups` |
| `just restore <file>` | Put a copy back, writers stopped first |

`just gate` green is the precondition for a commit. Not a suggestion: CI runs the same four and
blocks on them.

## Deploying to a VPS

The host is a VPS running this stack with gunicorn, decided by the owner. **The rest of deployment
is genuinely undecided and this file will not pretend otherwise**: whether Cloudflare fronts it by
Tunnel or by proxied DNS is open question OQ-2 in `specs/foundation.md`, and backlog item B11 is
blocked on it. What follows is the part that is settled.

Build and run exactly what you run locally. Development and production differ in configuration,
never in architecture.

```bash
cp .env.example .env     # on the host, filled with real values, never committed
chown 1000 backups       # the container runs as uid 1000 and this directory is bind mounted
docker compose up -d --build web backup
```

That `chown` is not decoration. The image creates its own unprivileged user and the backup
directory is mounted from the host, so its owner is whoever cloned the repository. Clone as root,
which is the normal thing on a server, and the container cannot write there: the copy fails every
day and the failure reads as `unable to open database file`, which sends the reader hunting a
corrupt database that does not exist. The command now refuses with the directory named instead,
but the `chown` is what makes it unnecessary.

**The `scheduler` service is deliberately absent from that line.** An owner decision of 2026-08-31
ships this in two phases: the first one is registration and the export, with no WhatsApp delivery,
because there is nothing worth notifying anybody about until the registry has something in it. The
host has no gateway configured yet, so a send fails loudly by design, and a scheduler started
now would mark every morning's list failed and retry it every hour for the rest of the day. Phase
two, the procedure further down under turning the WhatsApp list on, adds
`scheduler` to that command once the adapter exists. The `backup` service does run from day one,
because the registry the first phase accumulates is then the only asset the company owns.

Six things that are specific to production:

**`DJANGO_DEBUG=0`.** Then `DJANGO_ALLOWED_HOSTS` must carry the real hostname and must still carry
`127.0.0.1` for the healthcheck.

**A fresh `DJANGO_SECRET_KEY`,** generated on the host and never existing anywhere else. The
production `DEADLINER_SECRET_PATH_SEGMENT` is a short chosen word since 2026-08-31 and guards
nothing, so the only rule left for it is that it is a valid segment.

**Client IP and country come from Cloudflare's forwarding headers only**, which is what makes the
audit trail meaningful, and that trust is only sound if every request really does arrive through
Cloudflare. Direct access to the origin defeats it.

**Do not turn on gunicorn's access log.** It ignores Django's logging configuration entirely, so
`--access-logfile` writes the full request path straight past the redaction filter and the segment
lands in a log file, which is the one thing invariant I7 exists to prevent. I7 stands even though
the segment stopped being secret, because withdrawing an invariant is its own decision.

**Back up the volume, not the container.** Everything the company owns is the SQLite file on
`notification-system_data`. The `backup` service above does this daily; the section on backups and
restore is what to read before you need it, not after. Start the `backup` service beside `web` and read the next section,
which is the whole procedure including the restore.

Static files are handled: WhiteNoise serves them and `collectstatic` runs during the image build,
under the secret segment like everything else.

### Turning the WhatsApp list on

Phase two, in the order that keeps a mistake from reaching the group. Everything runs on the
production host, from the directory holding `compose.yaml`. The recipes named `just evolution-*`
do the same calls where `just` and `jq` are installed; the plain commands are given because a
server usually has neither.

1. **Before pulling the new code, confirm the old alert table is empty.** The migration that ships
   with this version deletes it, and it should hold nothing because the scheduler never ran here.

   ```bash
   docker compose exec web python manage.py shell -c "from django.db import connection; c = connection.cursor(); c.execute('select count(*) from core_alert'); print(c.fetchone()[0])"
   ```

   It must print `0`. If it prints anything else, stop and ask before going on.

2. **Edit `.env`.** Add the eight message lines from `.env.example` exactly as they are there
   (`DEADLINER_SEND_TIME`, `DEADLINER_MESSAGE_HEADER`, `DEADLINER_MESSAGE_TEMPLATE` replacing the
   old one, and the five `DEADLINER_DEADLINE_` phrases). Then the gateway:

   ```bash
   EVOLUTION_BASE_URL=http://evolution:8080
   EVOLUTION_INSTANCE_NAME=valeverde
   ```

   `EVOLUTION_API_KEY` and `EVOLUTION_DB_PASSWORD` are already there. If port 8080 is taken on the
   host, check with `ss -ltn | grep 8080`, set `EVOLUTION_PORT` to a free one and use that port
   wherever `8080` appears in the `curl` commands below. `EVOLUTION_BASE_URL` stays
   `http://evolution:8080` either way, because that is the address inside the Docker network.

3. **Update and restart the application, still without the scheduler.**

   ```bash
   git pull
   docker compose up -d --build web backup
   docker compose ps
   ```

   `web` has to come back healthy. If it restarts in a loop, `docker compose logs web` names the
   variable that is missing or malformed.

4. **Read the message that would be sent.** Nothing is sent by this.

   ```bash
   docker compose exec web python manage.py send_alerts --preview
   ```

5. **Start Evolution and create the instance.**

   ```bash
   docker compose up -d evolution
   set -a; . ./.env; set +a
   curl -s http://127.0.0.1:8080/
   curl -s -X POST http://127.0.0.1:8080/instance/create -H "apikey: $EVOLUTION_API_KEY" -H "Content-Type: application/json" -d '{"instanceName":"valeverde","integration":"WHATSAPP-BAILEYS","qrcode":true}'
   ```

   The first `curl` answers with the version, `2.3.7`. Give the service a minute on its first
   start, since it runs its own database migrations.

6. **Pair the company phone.** The pairing done on a development machine in October lives on that
   machine; this host pairs again. The QR code rotates every few seconds, so it has to be read
   from something that refreshes it. From your own computer, open a tunnel to the host and use
   Evolution's manager screen:

   ```bash
   ssh -L 8080:127.0.0.1:8080 user@the-host
   ```

   Then open `http://localhost:8080/manager` in a browser on your computer, sign in with the value
   of `EVOLUTION_API_KEY`, open the instance `valeverde` and scan its QR code with the company
   phone, in WhatsApp under linked devices. Back on the host, confirm:

   ```bash
   curl -s http://127.0.0.1:8080/instance/connectionState/valeverde -H "apikey: $EVOLUTION_API_KEY"
   ```

   The state has to read `open`.

7. **Read the group identifier from the vendor and compare it with `.env`.** It is never typed
   from memory.

   ```bash
   curl -s "http://127.0.0.1:8080/group/fetchAllGroups/valeverde?getParticipants=false" -H "apikey: $EVOLUTION_API_KEY"
   grep DEADLINER_WHATSAPP_DESTINATION .env
   ```

   Find the group by its `subject` in the answer and make sure its `id`, which ends in `@g.us`, is
   the value in `.env`. If you change `.env`, run step 3 again.

8. **Send one test message to the group through the gateway.**

   ```bash
   curl -s -X POST http://127.0.0.1:8080/message/sendText/valeverde -H "apikey: $EVOLUTION_API_KEY" -H "Content-Type: application/json" -d "{\"number\":\"$DEADLINER_WHATSAPP_DESTINATION\",\"text\":\"Teste do sistema de avisos\"}"
   ```

   Somebody has to see it arrive on a phone. An answer from the gateway is acceptance, not
   delivery.

9. **Start the scheduler.**

   ```bash
   docker compose up -d --build web backup scheduler
   ```

   From here the command is polled every minute. If it is already past the send time and no list
   went out today, the list is sent within a minute, which is the rule and not a defect: late
   beats never. To wait for tomorrow morning instead, start the scheduler after midnight, or
   before the send time.

10. **Look at the list screen.** It says whether today's list was sent, and when, or that it
    failed and when it is tried again. `docker compose logs scheduler` shows one `list_send` line
    per attempt, with the number of services and the length of the message.

To turn it off again: `docker compose stop scheduler`. Nothing is lost, and the next start sends
that day's list if it is still owed.

### The reverse proxy, on a host that already runs other things

The deployment host is shared with the company's institutional site and with Ecobalance, and its
nginx already fronts several services by hostname, each container published on the loopback address
only. This application joins that pattern rather than inventing another one, and it publishes on
the loopback address too, which is why `WEB_PORT` exists: pick one nothing else is using.

```bash
ss -tlnp | grep :8010 || echo "free"     # 8000 is taken on that host by Portainer
```

Write `/etc/nginx/sites-available/avisos.valeverdeambiental.com.br` with the plain HTTP server
first, because certbot's nginx plugin needs a block carrying the name before it can add TLS to it:

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name avisos.valeverdeambiental.com.br;

    location / {
        limit_req zone=avisos burst=40 nodelay;
        include proxy_params;
        proxy_pass http://127.0.0.1:8010;
    }
}
```

One `location` is the whole file, and that is not an oversight: this application serves its own
static assets through WhiteNoise, under the same path segment as everything else, so there is no
`alias` to write and no second route to expose. `include proxy_params` is what sends
`X-Forwarded-Proto`, confirmed present on that host, and the settings module turns it into
`request.is_secure()`; without that pair Django computes the CSRF origin as `http://` while the
browser sends `https://` and refuses every form in the application.

The rate limit needs its own zone, declared in the `http` block and therefore in its own file at
`/etc/nginx/conf.d/avisos-rate-limit.conf`:

```nginx
limit_req_zone $binary_remote_addr zone=avisos:10m rate=20r/s;
```

Its own zone and not the host's existing general one, because a shared zone counts this
application's requests against the same per address budget as the institutional site, and a small
company reaches its office behind one address. Twenty a second with a burst of forty is far above
what a person filling a form produces and far below what a script enumerating the link produces.

**This is not access control and does not pretend to be.** Foundation section 6 says the link is
open, so anyone holding or guessing it reads and writes everything; the limit bounds how fast that
can be done, and nothing else.

```bash
ln -s /etc/nginx/sites-available/avisos.valeverdeambiental.com.br /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
certbot --nginx -d avisos.valeverdeambiental.com.br
nginx -t && systemctl reload nginx
```

**`nginx -t` before every reload, without exception.** It validates the whole configuration, so a
mistake in this file is caught before the reload rather than after it, and the other sites on that
host never learn this one was deployed. That is the entire reason adding a service here is routine
instead of frightening.

When the zone moves to Cloudflare and this application goes behind a tunnel, this virtual host is
retired: the tunnel reaches the container directly and nginx stops being in the path. Remove the
certificate from certbot in the same pass, or its renewal starts failing for a name that no longer
resolves to this machine.

## Backups and restore

The database is one SQLite file on the `data` volume, and it is everything the company has. A
`docker compose down -v`, a migration that goes wrong, or one mistaken delete takes every client
deadline with it. So the stack runs a copy service:

```bash
docker compose up -d --build web backup
```

The `backup` service copies the database once a day into `./backups`, beside `compose.yaml` on the
host, where a person can reach the files and copy them off the machine. It is the shape the
scheduler had before it began polling every minute: a shell loop, no cron and no queue, sleeping a day after a copy and an hour after
a failure, which stays loud in `docker compose logs backup`.

Each copy is named for the moment it was taken, in the configured time zone, so the directory sorts
by name into chronological order:

```
backups/db-2026-08-31T12-56-44.sqlite3
backups/db-2026-09-01T12-56-51.sqlite3
```

The directory keeps the 14 most recent copies and deletes the rest, oldest first. Two weeks is long
enough for a bad migration or a mistaken delete to be noticed across a holiday, and a copy of this
database is under a megabyte. The number is a constant in `core/backups.py` and not a variable,
because I4 governs the business values the foundation names and how many copies a disk holds is not
one of them. Anything in that directory that is not one of these copies is never touched.

The copy goes through SQLite's own online backup API, never through `cp`. Copying the file of a
database that a writer is inside can produce a torn copy that does not open at all, and finding
that out on the day you need it is the whole failure this section exists to prevent.

Take one by hand at any time:

```bash
just backup
docker compose run --rm --no-deps -T backup python manage.py backup_database   # the same thing without just
```

### Restoring

Executed end to end on 2026-08-31, not merely written down. Stopping the writers first is the part
that matters: replacing the file under a live connection corrupts it.

```bash
ls backups/                                    # 1. pick the copy you want
docker compose stop web scheduler backup       # 2. nothing may be writing
docker compose run --rm --no-deps -T backup \
  sh -c "cp /backups/db-2026-08-31T12-56-44.sqlite3 /data/db.sqlite3 && rm -f /data/db.sqlite3-wal /data/db.sqlite3-shm"
docker compose up -d web backup                # 3. back in service
```

`just restore db-2026-08-31T12-56-44.sqlite3` does steps 2 and the copy, and prints the command for
step 3 rather than guessing which services you were running.

The journal files go with the restored database on purpose. A stale write ahead log left beside a
replaced file is replayed over it, which turns a good restore into a corrupt one.

### What this protects against, and what it does not

It protects against a destroyed volume, a migration that goes wrong, a mistaken delete, and a
database file that goes corrupt. Restoring costs a few minutes and the records entered since the
last copy.

It does not protect against losing the disk. The copies sit on the same machine as the database
they copy, so a dead VPS, a wiped host or a deleted account takes both. Nothing here replicates
them anywhere, because no off site destination has been decided. Copying `backups/` to another
machine periodically (`scp`, `rsync`, anything) is the missing half, and it is a decision for the
owner rather than something this file invents.

One operational detail. The `backups` directory is tracked with a `.gitkeep` so a fresh clone
already has it, owned by whoever cloned. If it is ever missing when the stack starts, Docker
creates it owned by root, the container user cannot write into it, and the daily run then fails
loudly every hour with the path in the message. The fix is `mkdir -p backups` before the first
start, or `sudo chown 1000:1000 backups` after the fact.

## Tests

```bash
just test              # the whole suite
just test -k catalogue # one slice
just gate              # what CI blocks on
```

Development is test first in two windows: one writes failing behaviour tests and implements
nothing, the next implements the minimum to turn them green and may not edit a test. Every test
names the invariant or requirement it implements. The method is `specs/testing.md` and it is not
optional.

## Open questions, so you do not go looking for what is not there

- **The WhatsApp integration is written and not yet switched on.** The daily list (backlog B27)
  and the adapter that hands it to Evolution API (backlog B8) are both in the code, and where no
  gateway is configured a send fails loudly instead of pretending. What remains is on the host and
  is the procedure under turning the WhatsApp list on. No real message has been sent by the
  adapter itself yet, only by hand during the spike.
- **OQ-2, the Cloudflare mechanism**, as above.
- **The message wording (OQ-3) closed on 2026-10-27** and its header changed on 2026-11-09. The
  text is the owner's voice and not a technical choice, and `.env.example` carries it.

## Troubleshooting

**`port is already allocated`.** Something else holds 8000. Either stop it or publish a different
one, without editing the tracked `compose.yaml`:

```bash
printf 'services:\n  web:\n    ports: !override\n      - "8010:8000"\n' > compose.override.yaml
docker compose up -d --build web
```

Compose reads `compose.override.yaml` automatically. Add it to `.gitignore`, since it is a fact
about your machine and not about the project. The `!override` tag is required: without it Compose
merges the two port lists and tries to bind both.

**`required variable EVOLUTION_API_KEY is missing a value`.** Compose interpolates the entire file
before it decides which service you asked for, so those keys are required even to start `web`
alone. Copy the current `.env.example`; an older `.env` predates them.

**Five complaints about missing `DEADLINER_*` variables.** You ran Python directly instead of
through `just`. See above.

**`http://localhost:8000/` returns 404.** Correct. The application is under the secret segment.

**The admin has no styling.** It should not happen any more, but if it does, `collectstatic` did
not run. Rebuild the image, or run `just setup` locally.
