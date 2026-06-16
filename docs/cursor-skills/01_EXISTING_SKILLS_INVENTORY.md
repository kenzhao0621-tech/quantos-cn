# Existing Skills Inventory

| Skill | Location | Scope | Purpose | Triggers | Dependencies | Risk | Status |
|-------|----------|-------|---------|----------|--------------|------|--------|
| automate | ~/.cursor/skills-cursor/automate | built-in | Cursor Automations | automation setup | local | low | ACTIVE |
| babysit | ~/.cursor/skills-cursor/babysit | built-in | PR merge-ready loop | PR triage | gh | low | ACTIVE |
| canvas | ~/.cursor/skills-cursor/canvas | built-in | Analytical React canvas | data-heavy artifacts | — | low | ACTIVE |
| create-hook | ~/.cursor/skills-cursor/create-hook | built-in | hooks.json authoring | create hook | — | low | ACTIVE |
| create-rule | ~/.cursor/skills-cursor/create-rule | built-in | Cursor rules | .cursor/rules | — | low | ACTIVE |
| create-skill | ~/.cursor/skills-cursor/create-skill | built-in | SKILL.md authoring | create skill | — | low | ACTIVE |
| create-subagent | ~/.cursor/skills-cursor/create-subagent | built-in | Custom subagents | new agent type | — | low | ACTIVE |
| loop | ~/.cursor/skills-cursor/loop | built-in | Recurring prompts | /loop | — | low | ACTIVE |
| migrate-to-skills | ~/.cursor/skills-cursor/migrate-to-skills | built-in | Rules→skills migration | migrate rules | — | low | ACTIVE |
| review | ~/.cursor/skills-cursor/review | built-in | Review router | code review | subagent | low | ACTIVE |
| review-bugbot | ~/.cursor/skills-cursor/review-bugbot | built-in | Bugbot review | /review-bugbot | — | low | ACTIVE |
| review-security | ~/.cursor/skills-cursor/review-security | built-in | Security review | /review-security | — | low | ACTIVE |
| sdk | ~/.cursor/skills-cursor/sdk | built-in | Cursor SDK guide | @cursor/sdk | — | low | ACTIVE |
| shell | ~/.cursor/skills-cursor/shell | built-in | Literal shell exec | /shell | — | medium | ACTIVE |
| split-to-prs | ~/.cursor/skills-cursor/split-to-prs | built-in | Split changes to PRs | split PR | gh | low | ACTIVE |
| statusline | ~/.cursor/skills-cursor/statusline | built-in | CLI status line | statusline | — | low | ACTIVE |
| update-cli-config | ~/.cursor/skills-cursor/update-cli-config | built-in | CLI config | cli-config.json | — | low | ACTIVE |
| update-cursor-settings | ~/.cursor/skills-cursor/update-cursor-settings | built-in | settings.json | editor settings | — | low | ACTIVE |
| cursor-skills-audit | ~/.cursor/skills/cursor-skills-audit | user | Skills audit workflow | audit skills | git | low | ACTIVE |
| find-skills | .cursor/skills/find-skills | project | Discover skills | find skill | npx skills | low | ACTIVE |
| brainstorming | .cursor/skills/brainstorming | project | Pre-implementation design | unclear requirements | node optional | low | ACTIVE |
| writing-plans | .cursor/skills/writing-plans | project | Implementation plans | approved spec | — | low | ACTIVE |
| frontend-design | .cursor/skills/frontend-design | project | UI implementation | build component | — | low | ACTIVE |
| humanizer | .cursor/skills/humanizer | project | Tone final pass | naturalize text | — | low | ACTIVE |
| markitdown | .cursor/skills/markitdown | project | Doc→Markdown | convert pdf | markitdown CLI | low | ACTIVE |
| short-video-opening-optimizer | .cursor/skills/short-video-opening-optimizer | project | Video hooks | TikTok hook | — | low | ACTIVE |
| certbot-ssl | .cursor/skills/certbot-ssl | project | SSL dry-run planner | certbot plan | certbot | medium | ACTIVE |

## Missing / empty paths

- `~/.cursor/skills/` — created for audit skill only (no other user skills yet)
- `~/.cursor/agents/` — not present
- `~/.cursor/rules/` — not present
- Project `.cursor/rules`, `.cursor/agents`, `hooks.json`, `AGENTS.md` — not present
- `~/.claude/skills/`, `~/.agents/skills/` — not present

## MCP (project session)

Enabled: cursor-app-control, cursor-ide-browser. Plugin MCP caches under `.cursor/projects/.../mcps/` (Azure, OpenSearch, AWS, etc.) — not modified by this audit.
