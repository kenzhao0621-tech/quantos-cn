---
name: release-docs
description: >-
  Write release notes and sync CHANGELOG.md from git history and GitHub releases
  (covers Release Notes + Changelog Miner). Adapter from alibaba/page-agent
  update-changelog. Use when drafting release notes, mining commits for changelog
  entries, or syncing docs/CHANGELOG.md. Requires gh CLI for release metadata.
  Do NOT invent versions or changes without git/gh evidence.
---

# Release Docs

**Adapter** — upstream: [alibaba/page-agent](https://github.com/alibaba/page-agent) `.agents/skills/update-changelog` @ `2802ab3deaf62ee863f8338f01e39b05c57924a0`

PRIMARY for release-notes and changelog-miner capabilities (single skill, no duplicate).

## Procedure

Follow the workflow in `SKILL.base.md` (vendored upstream body).

## Aliases

- release-notes → this skill
- changelog-miner → this skill (evidence gathering steps 3–4 in base)

## Negative triggers

- Developer doc authoring from code → markitdown / docs-whisperer patterns
- Dependency audit → dependency-guard

See `SOURCE.md`.
