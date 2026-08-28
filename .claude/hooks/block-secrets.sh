#!/usr/bin/env bash
# Blocks a secret or a database file from being staged, which is the point of no return.
#
# Foundation I5 makes this permanent: no secret in the repository, no production data outside
# production. In this project the concrete shapes are an env file carrying real values (the
# Evolution API key, the destination number, the secret access path) and the SQLite database,
# whose rows are real client data the moment the system is used. Once either reaches a remote
# it is permanent and external; reverting the commit does not undo it.
#
# PreToolUse on Bash. Exit 2 blocks the call before it runs.
set -euo pipefail

payload=$(cat)
tool=$(jq -r '.tool_name // empty' <<<"$payload")
[[ "$tool" == "Bash" ]] || exit 0

cmd=$(jq -r '.tool_input.command // empty' <<<"$payload")
grep -qE '\bgit +add\b' <<<"$cmd" || exit 0

# .env and its variants are refused; .env.example and .env.template are allowed because they
# carry placeholders by convention and are how the required keys are documented.
forbidden='(^|[ /"'"'"'])\.env([ "'"'"']|$)|\.env\.(local|dev|development|prod|production)([ "'"'"']|$)|\.sqlite3?([ "'"'"']|$)'

deny() {
  cat >&2 <<EOF
Blocked: this stages a secret or a database file, which never enters the repository (I5,
foundation section 9).

$1

Real values live only in the untracked env file; the repository documents the keys through
.env.example with placeholders. The database is data, not code. If this is a false positive,
the owner lifts it deliberately rather than the session working around it.
EOF
  exit 2
}

if grep -qE "$forbidden" <<<"$cmd"; then
  deny "Command: $cmd"
fi

# git add -A and git add . stage whatever is present, so they are refused while an untracked
# env file or database sits on disk, before a .gitignore exists to catch them.
if grep -qE '\bgit +add +(-A|--all|\.)( |$)' <<<"$cmd"; then
  root="${CLAUDE_PROJECT_DIR:-.}"
  if [[ -f "$root/.env" ]] || compgen -G "$root"/*.sqlite3 >/dev/null || compgen -G "$root"/*.sqlite >/dev/null; then
    deny "Command: $cmd
The tree currently holds an untracked env file or SQLite database, and this stages
everything. Stage the paths you mean, explicitly."
  fi
fi

exit 0
