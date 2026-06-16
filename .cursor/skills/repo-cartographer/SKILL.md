---
name: repo-cartographer
description: >-
  Map repository structure, modules, entry points, and dependency hubs before
  code changes. Primary repo map source (anthony-maio/cartograph repo-surveyor).
  Use before modifying unfamiliar code. Do NOT duplicate context-pack output.
---

Use this skill only when Cartograph itself is unavailable or when you need to manually verify its outputs.

Manual workflow:
1. Discover source, config, and entry files. Skip generated, vendored, and build output.
2. Rank likely-important files by entry points, fan-in, API surface, and root wiring role.
3. Trace the strongest dependency hubs instead of reading the whole tree.
4. Build the smallest useful file set for the current task.
5. Produce a doc-ready summary from that reduced set.

Output contract:
- Key files
- Dependency hubs
- Minimal task context
- Doc-ready summary

Rules:
- Prefer `use-cartograph` whenever the plugin, CLI, or MCP server becomes available.
- Keep manual reads narrow.
- Match the same output shape as `use-cartograph`.
