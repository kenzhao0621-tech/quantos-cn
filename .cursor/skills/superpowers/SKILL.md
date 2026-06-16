---
name: superpowers
description: >-
  Orchestrates obra/superpowers workflow sub-skills for structured development.
  Use when user wants the full Superpowers methodology. Routes to brainstorming,
  writing-plans, executing-plans, TDD, debugging, and code review sub-skills.
  Do NOT use for single-step fixes or when a narrower skill already applies.
disable-model-invocation: true
---

# Superpowers Router

Do not duplicate sub-skill content. Invoke the appropriate sub-skill by name:

| Stage | Sub-skill |
|-------|-----------|
| Ideation | brainstorming |
| Context | context-pack |
| Plan | writing-plans |
| Long-running state | planning-with-files |
| Execute | executing-plans or subagent-driven-development |
| TDD | test-driven-development |
| Debug | systematic-debugging |
| Review | requesting-code-review / receiving-code-review |
| Verify | verification-before-completion |

See `.cursor/skills/SKILL_ROUTING.md` for trigger boundaries.
