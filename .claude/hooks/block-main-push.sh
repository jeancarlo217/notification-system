#!/usr/bin/env bash
# Blocks a direct push touching main. Branch and pull request always; main never receives a
# direct push (CLAUDE.md standing rules). Until branch protection exists on the remote, this
# hook is the only mechanical guard the rule has. Honest limit: it covers sessions running
# this toolkit, not a bare terminal.
#
# PreToolUse on Bash. Exit 2 blocks the call before it runs.
set -euo pipefail

payload=$(cat)
tool=$(jq -r '.tool_name // empty' <<<"$payload")
[[ "$tool" == "Bash" ]] || exit 0

cmd=$(jq -r '.tool_input.command // empty' <<<"$payload")
grep -qE '\bgit\b[^|&;]*\bpush\b' <<<"$cmd" || exit 0

deny() {
  cat >&2 <<EOF
Blocked: direct push touching main. Branch and pull request always; main never receives a
direct push (CLAUDE.md standing rules).

$1

Create a branch for the work and push that. If this is a false positive, the owner lifts it
deliberately rather than the session working around it.
EOF
  exit 2
}

# A push that names main as a refspec is refused outright. \bmain\b also matches a branch
# like feature/main-page: that false positive is accepted, fail closed.
if grep -qE '\bmain\b' <<<"$cmd"; then
  deny "Command: $cmd
It names main."
fi

# A push with no refspec pushes the current branch, so any push while main is checked out
# is refused, including one that names another ref, fail closed.
branch=$(git -C "${CLAUDE_PROJECT_DIR:-.}" branch --show-current 2>/dev/null || true)
if [[ "$branch" == "main" ]]; then
  deny "Command: $cmd
The current branch is main, so this pushes main."
fi

exit 0
