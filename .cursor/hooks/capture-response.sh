#!/bin/bash
# Ralph Loop: detect completion promise in agent response.
# Source: cursor/plugins ralph-loop (pinned in SOURCE.md)
set -euo pipefail

PROJECT_DIR="${CURSOR_PROJECT_DIR:-.}"
STATE_FILE="$PROJECT_DIR/.cursor/ralph/scratchpad.md"
DONE_FLAG="$PROJECT_DIR/.cursor/ralph/done"

[[ -f "$STATE_FILE" ]] || exit 0

FRONTMATTER=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' "$STATE_FILE")
COMPLETION_PROMISE=$(echo "$FRONTMATTER" | grep '^completion_promise:' | sed 's/completion_promise: *//' | sed 's/^"\(.*\)"$/\1/')

[[ "$COMPLETION_PROMISE" != "null" ]] && [[ -n "$COMPLETION_PROMISE" ]] || exit 0

# Hook input is JSON with agent response text in hook-specific fields
HOOK_INPUT=$(cat)
if echo "$HOOK_INPUT" | grep -q "$COMPLETION_PROMISE"; then
  mkdir -p "$(dirname "$DONE_FLAG")"
  touch "$DONE_FLAG"
fi

exit 0
