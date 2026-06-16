# Rollback Guide

## Backup location

```
.cursor-backups/skills-audit-20260616-143447/
├── builtin-skills-cursor/names.txt
└── user-skills/          (empty snapshot — no prior user skills)
```

## Full rollback (project)

```bash
cd /Users/kenzhao/Projects/netlify-demo
git checkout main
git branch -D chore/cursor-skills-audit   # optional — only if abandoning branch
rm -rf .cursor/skills .cursor/skill-sources docs/cursor-skills .cursor-backups/skills-audit-20260616-143447
```

## Partial rollback (single skill)

```bash
rm -rf .cursor/skills/<skill-name>
```

## User-level audit skill rollback

```bash
rm -rf ~/.cursor/skills/cursor-skills-audit
```

## Restore from backup

```bash
cp -R .cursor-backups/skills-audit-20260616-143447/project/.cursor/* .cursor/ 2>/dev/null || true
```

## Git

- Branch: `chore/cursor-skills-audit` (not pushed)
- To undo uncommitted: `git checkout main && git branch -D chore/cursor-skills-audit`
