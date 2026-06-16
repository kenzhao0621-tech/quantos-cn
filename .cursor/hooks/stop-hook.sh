#!/bin/bash
# Ralph Loop stop hook — cursor/plugins ralph-loop (user-authorized, max_iterations required)
set -euo pipefail

HOOK_INPUT=$(cat)

PROJECT_DIR="${CURSOR_PROJECT_DIR:-.}"
STATE_FILE="$PROJECT_DIR/.cursor/ralph/scratchpad.md"
DONE_FLAG="$PROJECT_DIR/.cursor/ralph/done"

if [[ ! -f "$STATE_FILE" ]]; then
  exit 0
fi

FRONTMATTER=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' "$STATE_FILE")
ITERATION=$(echo "$FRONTMATTER" | grep '^iteration:' | sed 's/iteration: *//')
MAX_ITERATIONS=$(echo "$FRONTMATTER" | grep '^max_iterations:' | sed 's/max_iterations: *//')
COMPLETION_PROMISE=$(echo "$FRONTMATTER" | grep '^completion_promise:' | sed 's/completion_promise: *//' | sed 's/^"\(.*\)"$/\1/')

if [[ ! "$ITERATION" =~ ^[0-9]+$ ]] || [[ ! "$MAX_ITERATIONS" =~ ^[0-9]+$ ]]; then
  echo "Ralph loop: state file corrupted. Stopping." >&2
  rm -f "$STATE_FILE" "$DONE_FLAG"
  exit 0
fi

if [[ -f "$DONE_FLAG" ]]; then
  rm -f "$STATE_FILE" "$DONE_FLAG"
  exit 0
fi

if [[ $MAX_ITERATIONS -gt 0 ]] && [[ $ITERATION -ge $MAX_ITERATIONS ]]; then
  echo "Ralph loop: max iterations ($MAX_ITERATIONS) reached." >&2
  rm -f "$STATE_FILE" "$DONE_FLAG"
  exit 0
fi

PROMPT_TEXT=$(awk '/^---$/{i++; next} i>=2' "$STATE_FILE")
if [[ -z "$PROMPT_TEXT" ]]; then
  rm -f "$STATE_FILE" "$DONE_FLAG"
  exit 0
fi

NEXT_ITERATION=$((ITERATION + 1))
TEMP_FILE="${STATE_FILE}.tmp.$$"
sed "s/^iteration: .*/iteration: $NEXT_ITERATION/" "$STATE_FILE" > "$TEMP_FILE"
mv "$TEMP_FILE" "$STATE_FILE"

if [[ "$COMPLETION_PROMISE" != "null" ]] && [[ -n "$COMPLETION_PROMISE" ]]; then
  HEADER="[Ralph loop iteration $NEXT_ITERATION. To complete: output $COMPLETION_PROMISE ONLY when genuinely true.]"
else
  HEADER="[Ralph loop iteration $NEXT_ITERATION.]"
fi

FOLLOWUP="$HEADER

$PROMPT_TEXT"

jq -n --arg msg "$FOLLOWUP" '{"followup_message": $msg}'
exit 0
