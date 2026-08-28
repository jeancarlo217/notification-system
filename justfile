# Commands for the deadline notification system. CLAUDE.md lists them; keep both in sync.

set dotenv-load := true

python := if os_family() == "windows" { "venv/Scripts/python.exe" } else { "venv/bin/python" }
evolution_url := env_var_or_default("EVOLUTION_SERVER_URL", "http://localhost:8080")

# List the recipes
default:
    @just --list

# First-time setup: virtualenv, dependencies, and the untracked .env from the example
setup:
    python -m venv venv
    {{python}} -m pip install -r requirements-dev.txt
    cp -n .env.example .env

# Run the development server
dev:
    {{python}} manage.py runserver

# Run any manage.py command, for example: just manage migrate
manage *ARGS:
    {{python}} manage.py {{ARGS}}

# Lint and check formatting
lint:
    {{python}} -m ruff check .
    {{python}} -m ruff format --check .

# Apply formatting and safe lint fixes
format:
    {{python}} -m ruff format .
    {{python}} -m ruff check --fix .

# Static types, mypy --strict with django-stubs
typecheck:
    {{python}} -m mypy

# Run the test suite, extra arguments go to pytest
test *ARGS:
    {{python}} -m pytest {{ARGS}}

# Scan the working tree for secrets with the tool CI runs (foundation I5)
secret-scan:
    MSYS_NO_PATHCONV=1 docker run --rm -v "{{justfile_directory()}}:/repo" ghcr.io/gitleaks/gitleaks:v8.30.1 dir /repo --redact --exit-code 1

# Everything CI blocks on, in CI order
gate: lint typecheck test secret-scan

# Bring the whole stack up: web, Evolution API and its Postgres and Redis
up:
    docker compose up --build

# Stop the stack
down:
    docker compose down

# Evolution API spike (B8, closes OQ-1). Needs Docker, curl, jq and the EVOLUTION_* keys in .env.

# Start only Evolution API with its Postgres and Redis
evolution-up:
    docker compose up -d evolution

# Version and status of the running Evolution API
evolution-status:
    curl -s {{evolution_url}}/ | jq .

# Create the WhatsApp instance (once); the phone is paired afterwards with evolution-qr
evolution-instance name="valeverde":
    curl -s -X POST {{evolution_url}}/instance/create -H "apikey: $EVOLUTION_API_KEY" -H "Content-Type: application/json" -d '{"instanceName":"{{name}}","integration":"WHATSAPP-BAILEYS","qrcode":true}' | jq '{instance, hash}'

# Save the pairing QR code to .evolution-qr.png (untracked); scan it with the company phone
evolution-qr name="valeverde":
    curl -s {{evolution_url}}/instance/connect/{{name}} -H "apikey: $EVOLUTION_API_KEY" | {{python}} -c "import sys, json, base64; d = json.load(sys.stdin); open('.evolution-qr.png', 'wb').write(base64.b64decode(d['base64'].split(',', 1)[1])); print('QR saved to .evolution-qr.png; pairing code:', d.get('pairingCode'))"

# Connection state of the instance: open means paired
evolution-state name="valeverde":
    curl -s {{evolution_url}}/instance/connectionState/{{name}} -H "apikey: $EVOLUTION_API_KEY" | jq .

# Send one text message, for example: just evolution-send 5567999999999 "teste"
evolution-send number text name="valeverde":
    curl -s -X POST {{evolution_url}}/message/sendText/{{name}} -H "apikey: $EVOLUTION_API_KEY" -H "Content-Type: application/json" -d '{"number":"{{number}}","text":"{{text}}"}' | jq '{id: .key.id, status}'
