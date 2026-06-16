# Source and Security Audit

## Verified upstream (≥2 signals each)

| Skill | Repository | Stars | License | Signals |
|-------|------------|-------|---------|---------|
| find-skills | vercel-labs/skills | 22K+ | MIT | README + SKILL.md |
| frontend-design | anthropics/skills | official | Anthropic terms | SKILL.md + LICENSE.txt |
| brainstorming | obra/superpowers | 57K+ | MIT | SKILL.md + README |
| writing-plans | obra/superpowers | 57K+ | MIT | SKILL.md + workflow docs |
| humanizer | blader/humanizer | 24K+ | MIT | SKILL.md + README |
| markitdown | coroboros/agent-skills → microsoft/markitdown | MIT | SKILL.md + PyPI |
| short-video-opening-optimizer | PostPlusAI/hook-skills | MIT | SKILL.md + hook-principles.md |
| certbot-ssl | local adapter | n/a | dry-run policy only |

## Security scan results

| Path | Finding | Severity | Action |
|------|---------|----------|--------|
| brainstorming/scripts/stop-server.sh | `rm -rf` only under `/tmp/*` | low | PASS — scoped cleanup |
| markitdown/scripts/markitdown.sh | writes to ~/.claude/output when -s | low | PASS — documented |
| find-skills/SKILL.md | references npx skills | low | PASS — no auto-exec |
| skill-sources/ | git clones for provenance | info | kept in .cursor/skill-sources/ |

No `curl | bash`, no sudo in installed skill scripts, no credential reads in SKILL.md.

## Unresolved / rejected sources

| Requested | Issue | Status |
|-----------|-------|--------|
| serper-scrape | liuxingqitd/serper-scrape — 2 stars, needs SERPER_API_KEY | UNRESOLVED |
| videocut | ZhaofanQiu/video_cut_skill — OpenClaw-focused, ffmpeg deps | NEED_USER_CONFIRMATION |
| ui-ux-pro-max | Broad description conflicts; needs uipro CLI | BLOCKED_BY_AUTHORIZATION |
| impeccable | Overlaps frontend-design; npx installer | DEFERRED |
| agent-reach | Heavy CLI deps, network, optional cookies | BLOCKED_BY_CREDENTIAL |
| trading-agents | TauricResearch/TradingAgents — framework not SKILL.md; live trading risk | QUARANTINE HIGH_RISK |
