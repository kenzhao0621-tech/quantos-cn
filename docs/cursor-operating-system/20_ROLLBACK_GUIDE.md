# Rollback Guide — Cursor Operating System

**Backup (OS Phase 0)**: `.cursor-backups/os-audit-20260616-152306/`  
**Backup (Skills audit Round 1)**: `.cursor-backups/skills-audit-20260616-143447/`

## Quick restore — OS branch only

```bash
cd /Users/kenzhao/Projects/netlify-demo
git checkout chore/cursor-skills-audit   # pre-OS branch
# or
git checkout main                        # if merged
```

## Restore project skills from OS backup

```bash
BACKUP=.cursor-backups/os-audit-20260616-152306
rm -rf .cursor/skills
rsync -a "$BACKUP/project-skills/" .cursor/skills/
```

## Restore user skills

```bash
BACKUP=.cursor-backups/os-audit-20260616-152306
rsync -a "$BACKUP/user-skills/" ~/.cursor/skills/
```

## Remove ralph-loop hooks

```bash
rm -f .cursor/hooks.json
rm -rf .cursor/hooks/
```

## Remove OS-only skills (Phase 1+)

```bash
rm -rf .cursor/skills/image-analysis-router
rm -rf .cursor/skills/web-content-safety-gate
rm -rf .cursor/skills/licensed-media-finder
rm -rf .cursor/skills/diagram-architect
rm -rf .cursor/skills/mermaid-renderer
rm -rf .cursor/agents
```

## Remove OS documentation only

```bash
rm -rf docs/cursor-operating-system docs/ai
```

## Full reset to pre-audit (destructive to cursor config)

```bash
git checkout main
rm -rf .cursor/skills .cursor/hooks .cursor/hooks.json .cursor/agents docs/cursor-skills docs/cursor-operating-system docs/ai
```

## agent-reach venv

```bash
rm -rf .cursor/skill-sources/agent-reach/.venv
# skill-sources is gitignored; sparse clone remains
```

## Record changes

Every install commit should update `docs/ai/DECISIONS.md` and `MANIFEST.json` with file list and upstream commit SHA.
