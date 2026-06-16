---
name: ralph-loop
description: >-
  Controlled iterative loop with mandatory max_iterations and completion promise.
  INSTALLED_DISABLED_BY_DEFAULT — enable only with explicit user authorization,
  time/token limits, and stop conditions. Do NOT use as default task entry.
disable-model-invocation: true
---

# Ralph Loop

## Trigger

The user wants to start a Ralph loop. An iterative development loop where the same prompt is fed back after every turn, and the agent sees its own previous work each iteration.

## Workflow

1. Gather the user's task prompt and optional parameters:
   - `max_iterations` (number, default 0 for unlimited)
   - `completion_promise` (text, or "null" if not set)

2. Create the directory `.cursor/ralph/` if it doesn't exist, then write the state file at `.cursor/ralph/scratchpad.md` with this exact format:

   ```markdown
   ---
   iteration: 1
   max_iterations: <N or 0>
   completion_promise: "<TEXT>" or null
   ---

   <the user's task prompt goes here>
   ```

   Example:
   ```markdown
   ---
   iteration: 1
   max_iterations: 20
   completion_promise: "COMPLETE"
   ---

   Build a REST API for todos with CRUD operations, input validation, and tests.
   ```

3. Confirm to the user that the Ralph loop is active, then begin working on the task.

4. The stop hook automatically intercepts each turn end and feeds the same prompt back as a followup message. You will see it prefixed with `[Ralph loop iteration N.]`.

## Guardrails

- If a completion promise is set, you may ONLY output `<promise>TEXT</promise>` when the statement is completely and genuinely true.
- Do not output false promises to escape the loop.
- Always recommend setting `max_iterations` as a safety net.
- Quote the `completion_promise` value in the YAML frontmatter if it contains special characters.

## Output

Confirm the loop is active (prompt, iteration limit, promise if set), then start working on the task immediately.
