# Skill Routing (PRIMARY / FALLBACK)

Canonical file: `.cursor/skills/SKILL_ROUTING.md`

## PRIMARY routing table

| Intent | PRIMARY | FALLBACK | Subskill of |
|--------|---------|----------|-------------|
| Skill discovery | find-skills | skills.sh manual | — |
| Ideation | brainstorming | superpowers | Superpowers |
| Task context pack | context-pack | repo-cartographer | — |
| Repo map | repo-cartographer | context-pack | — |
| Implementation plan | writing-plans | planning-with-files | Superpowers |
| Long-running state | planning-with-files | — | — |
| Execute plan | executing-plans | subagent-driven-development | Superpowers |
| TDD | test-driven-development | test-pilot | Superpowers |
| Test strategy | test-pilot | test-driven-development | adapter |
| E2E web tests | webapp-testing | — | anthropics |
| Code review | code-review | review-bugbot | → requesting-code-review |
| Debug | debug-radar | systematic-debugging | → systematic-debugging |
| CI failure | ci-fixer | debug-radar | cursor/plugins |
| Simplify code | code-simplifier | — | getsentry |
| UI design research | ui-ux-pro-max | frontend-design | nextlevelbuilder |
| UI implementation | frontend-design | — | anthropics |
| UI polish | impeccable | — | pbakaus |
| Docs convert | markitdown | — | coroboros |
| MCP server build | mcp-builder | create-skill | anthropics |
| Create skill | create-skill (built-in) | find-skills | Cursor |
| PPTX | pptx | — | anthropics |
| Ship gate | ship-checklist | verification-before-completion | adapter |
| Internet fetch | agent-reach | WebSearch | BLOCKED creds |
| Ralph loop | ralph-loop | — | DISABLED default |
| SSL plan | certbot-ssl | — | local adapter |
| Video hooks | short-video-opening-optimizer | — | PostPlusAI |
| Tone pass | humanizer | — | blader |

## Pipelines

### New feature
brainstorming → context-pack → repo-cartographer → writing-plans → planning-with-files → test-driven-development → frontend-design/API → test-pilot → webapp-testing → code-review → ship-checklist

### Frontend
ui-ux-pro-max → frontend-design → webapp-testing → impeccable → ship-checklist

### Bug fix
debug-radar → minimal fix → test-pilot → code-review

### CI failure
ci-fixer → (if not CI) systematic-debugging

### Refactor
repo-cartographer → Refactor Lens UNRESOLVED → tests → code-simplifier

### Release docs
Changelog Miner UNRESOLVED → Docs Whisperer UNRESOLVED → Release Notes UNRESOLVED → ship-checklist

### Skill extension
find-skills → audit → create-skill → mcp-builder (if MCP needed)

## Negative triggers (must NOT co-activate)

- planning-with-files + writing-plans on same entry (pick one stage)
- ui-ux-pro-max + frontend-design + impeccable on "fix one TS error"
- agent-reach + last30days (last30days not installed)
- ralph-loop without max_iterations
