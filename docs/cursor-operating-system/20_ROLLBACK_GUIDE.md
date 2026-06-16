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

## Remove MarkItDown venv

```bash
rm -rf .venv-markitdown
```

## Remove batch-2 skills

```bash
rm -rf .cursor/skills/refactor-lens .cursor/skills/release-docs .cursor/skills/dependency-guard
rm -rf .cursor/skills/paper-intake .cursor/skills/paper-structure-analyzer
rm -rf .cursor/skills/section-by-section-reader .cursor/skills/figure-table-extractor
rm -rf .cursor/skills/citation-graph-builder .cursor/skills/research-synthesis
rm -rf .cursor/skills/research-integrity-guard .cursor/skills/document-intake
rm -rf .cursor/skills/document-conversion-qa
rm -rf .cursor/agents/product-architect.md .cursor/agents/system-architect.md
# ... or rm -rf .cursor/agents and restore from backup
```

```bash
rm -rf .cursor/skill-sources/agent-reach/.venv
# skill-sources is gitignored; sparse clone remains
```

## Remove China quant stack

```bash
rm -rf .venv-china-quant
rm -rf tools/china_quant
rm -rf .cursor/skills/china-a-share-daily-trading-outlook
rm -rf .cursor/skills/china-a-share-quant-research
rm -rf .cursor/skills/china-market-rules-engine
rm -rf .cursor/skills/china-quant-data-quality-guard
rm -rf .cursor/skills/china-a-share-factor-lab
rm -rf .cursor/skills/china-a-share-backtest-engine
rm -rf .cursor/skills/china-equity-risk-model
rm -rf .cursor/skills/china-a-share-event-study
rm -rf docs/test-fixtures/china-quant
rm -f scripts/run-china-quant-tests.py
rm -f docs/ai/CHINA_QUANT.md docs/cursor-operating-system/24_CHINA_QUANT_STATUS.md
# Keep ledger history unless full reset:
# rm -rf docs/ai/daily-trading
```

## Record changes

Every install commit should update `docs/ai/DECISIONS.md` and `MANIFEST.json` with file list and upstream commit SHA.
