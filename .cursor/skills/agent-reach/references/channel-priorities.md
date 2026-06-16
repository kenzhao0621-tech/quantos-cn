# Agent Reach — Channel Priorities

**Policy date**: 2026-06-16  
**Do not**: request cookies, private sessions, paid APIs without user gate, or bypass platform restrictions.

## Priority 1 — enable first (public information)

| Channel | Backend | Setup |
|---------|---------|-------|
| General web pages | Jina Reader (`web`) | **ok** — default for URLs |
| RSS/Atom | feedparser | **ok** |
| GitHub public repos | gh CLI | `gh auth login` |
| Official docs | web + Exa (optional) | web ok; Exa needs mcporter |
| YouTube metadata/transcripts | yt-dlp | install in venv (partial) |

**Routing**: Prefer `web`, `rss`, `github`, `youtube` before any social platform.

## Priority 2 — when task requires it

| Channel | Notes |
|---------|-------|
| Reddit public | Requires login backend; no cookie extraction — user configures rdt-cli or OpenCLI themselves |
| arXiv / research | Use web + Semantic Scholar (Phase 3); not agent-reach primary |
| V2EX | **ok** — public API |
| Bilibili search | **ok** — search API only |

## Priority 3 — disabled until genuinely needed

Do **not** invoke by default:

- X/Twitter (`twitter`)
- Xiaohongshu (`xiaohongshu`)
- LinkedIn (`linkedin`)
- Xueqiu (`xueqiu`) — login cookie required
- Exa paid search — unless user configures mcporter + key
- OpenCLI cookie-reuse flows — **never** run `configure --from-browser` autonomously

## Doctor-first

Run `agent-reach doctor --json` before multi-platform research. Skip P3 channels unless user explicitly names the platform.

## Negative triggers

- Private accounts, DMs, paywalled content
- Cookie harvest / browser session export
- Stock/trading execution paths
