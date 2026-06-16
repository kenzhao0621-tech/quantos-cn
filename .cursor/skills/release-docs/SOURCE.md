# Source — release-docs

| Field | Value |
|-------|-------|
| Upstream | https://github.com/alibaba/page-agent |
| Path | `.agents/skills/update-changelog/SKILL.md` |
| Author | alibaba |
| License | MIT |
| Pinned commit | `2802ab3deaf62ee863f8338f01e39b05c57924a0` |
| Installed | 2026-06-16 |
| Decision | INSTALL (PRIMARY for release-notes + changelog-miner) |
| Scripts | gh CLI only (runtime) |
| Network | gh API when user runs release commands |
| Credentials | gh auth (user-level, not in repo) |
| Rejected duplicate | CuriousLearner/devkit changelog-generator |

Rollback: `rm -rf .cursor/skills/release-docs`
