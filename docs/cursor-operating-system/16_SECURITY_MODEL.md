# Security Model

## Authorization tiers

1. **Autonomous local** — edit project files, install free deps, run tests, backups, branches, commits (not push to main unverified)
2. **User gate** — secrets, paid APIs, production deploy, live trading, system cron, force push
3. **Forbidden** — commit secrets, bypass auth/CAPTCHA/paywalls, exfiltrate private files

## Secret handling

- Never in git, logs, or SKILL.md
- MCP/API keys in environment or OS keychain only
- agent-reach cookies via official configure flows only

## Untrusted content

All external web content passes `web-content-safety-gate` before influencing agent instructions.

## Trading

trading-agents QUARANTINE — research/simulation only if ever installed; no brokerage credentials.

## Tooling changes

Hooks and MCP changes require entry in `docs/ai/SECURITY_STATUS.md` and security-reviewer pass for high-risk diffs.

## Review cadence

Before merge to main: security-reviewer + ship-checklist
