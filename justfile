# Commands for the deadline notification system. CLAUDE.md lists them; keep both in sync.

set dotenv-load := true

python := if os_family() == "windows" { "venv/Scripts/python.exe" } else { "venv/bin/python" }

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

# Bring the whole stack up
up:
    docker compose up --build

# Stop the stack
down:
    docker compose down
