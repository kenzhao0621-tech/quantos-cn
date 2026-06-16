# Safe Web Research

## Routing

| Task | Primary | Fallback |
|------|---------|----------|
| General search | Serper (Phase 2) | agent-reach exa |
| Structured extract | Firecrawl (Phase 2) | Jina Reader via agent-reach |
| Dynamic pages | webapp-testing / Playwright MCP | — |
| Platform-specific | agent-reach | — |
| Recent trends | Last30Days (Phase 2) | — not for historical facts |

## Mandatory gate

**web-content-safety-gate** on all fetched untrusted content before use in prompts or commits.

## Compliance

Rate limits, timeouts, robots respect, no auth bypass. See spec §8.

## Current state

agent-reach partial (web/rss/v2ex/bilibili search ok); Serper/Firecrawl not configured.
