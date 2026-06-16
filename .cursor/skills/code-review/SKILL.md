---
name: code-review
description: >-
  Review code diffs for correctness, security, maintainability, and test coverage.
  Use when user asks for code review before merge. Routes to Superpowers
  requesting-code-review workflow. Do NOT use for automated CI fixes (ci-fixer)
  or built-in bugbot/security review unless explicitly requested.
disable-model-invocation: true
---

# Code Review

Load and follow `.cursor/skills/requesting-code-review/SKILL.md` for the review workflow.
For responding to review feedback, use `receiving-code-review`.
