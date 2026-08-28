#!/usr/bin/env bash
# Blocks an em dash or an en dash in prose, in any markdown this repository owns.
#
# Why a hook and not a rule: a prose rule is a request and a long session drops it. This is the
# enforcement half of the prose rule in CLAUDE.md.
#
# Two callers, one implementation. With no argument it is the PostToolUse hook on Write|Edit,
# reading one path from the payload on stdin; exit 2 blocks the turn and returns the message to the
# model. With paths as arguments it scans the tree (usable as a CI job later), reporting every file
# that fails rather than stopping at the first, and exiting 1.
set -euo pipefail

# grep -P refuses non-UTF-8 locales (observed on Git Bash for Windows, where the default C
# locale made the em dash check silently match nothing). Force a UTF-8 locale so the Unicode
# classes actually run.
export LC_ALL=C.UTF-8

report() {
  printf '%s\n\n%s\n\n%s\n' "$1" "$2" \
"CLAUDE.md forbids both, everywhere, including under .claude/. Replace with a comma, a period, or two
sentences. A CLI flag such as --strict is a flag and an arrow inside a fenced block is not prose; both
are already excluded, as is anything inside inline code." >&2
}

# The double hyphen half of the same rule.
# The pattern matches exactly two hyphens, never a longer run, because a thematic break,
# a table rule and a YAML fence are all three or more and are structure rather than prose. A bare
# --flag written outside backticks is flagged on purpose: the convention is that a flag is code.
DOUBLE='(^|[^-])--([^-]|$)'

# Returns 1 when the file carries a violation, 0 when it is clean or is not markdown this rule owns.
scan() {
  local path=$1 stripped
  [[ "$path" != *.md ]] && return 0
  [[ ! -f "$path" ]] && return 0

  # Fenced code blocks are not prose: a diagram arrow and a shell flag are not punctuation.
  # Inline code spans are stripped for the same reason, which is what lets `--strict` be written about.
  #
  # An excluded line is blanked rather than dropped, so `grep -n` below still numbers against the real
  # file. Dropping them renumbers everything after the first fence, and the caller is then told to look
  # at a line that does not carry the violation, which in CI is a filename plus a wrong number and no
  # editor to check it against.
  stripped=$(awk '/^[[:space:]]*```/{f=!f; print ""; next} f{print ""; next} {print}' "$path" |
    sed 's/`[^`]*`//g')

  if grep -qP '[\x{2014}\x{2013}]' <<<"$stripped"; then
    report "Em dash or en dash found in prose in $path." "$(grep -nP '[\x{2014}\x{2013}]' <<<"$stripped" | head -5)"
    return 1
  fi

  if grep -qE "$DOUBLE" <<<"$stripped"; then
    report "Double hyphen found in prose in $path." "$(grep -nE "$DOUBLE" <<<"$stripped" | head -5)"
    return 1
  fi

  return 0
}

if (($# > 0)); then
  status=0
  for argument in "$@"; do
    scan "$argument" || status=1
  done
  exit $status
fi

path=$(jq -r '.tool_input.file_path // empty')
[[ -z "$path" ]] && exit 0
scan "$path" || exit 2
exit 0
