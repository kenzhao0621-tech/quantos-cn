# OS Scenario A — Full-Stack Validation Fixture

Isolated test application proving the Cursor Operating System can coordinate a complete workflow.

## Run

```bash
node fixtures/os-scenario-a-fullstack/backend/server.js
# open http://127.0.0.1:3847
```

## Tests

```bash
node --test fixtures/os-scenario-a-fullstack/tests/unit.test.js
npx playwright test fixtures/os-scenario-a-fullstack/tests/e2e.spec.mjs
```

## Architecture

- **Frontend**: static HTML/CSS/JS (mobile-responsive)
- **Backend**: Node.js HTTP server + JSON file data layer
- **Port**: 3847 (override with `SCENARIO_A_PORT`)

See `ORCHESTRATION.md` for subagent handoffs and `FILE_OWNERSHIP.md` for write owners.
