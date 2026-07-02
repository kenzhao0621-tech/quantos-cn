# Next Phase Plan — post v2.3

## P0 — Data completeness

1. Complete warehouse backfill to 2018 (daily_bars, adj_factors, trade_calendar)
2. Wire CNINFO announcement fetch into DataTruthOS-verified pipeline
3. Replace sentiment placeholder with licensed or B-tier source only

## P1 — Kronos production path

1. Deploy Kronos sidecar on Render/Linux with pinned model weights
2. PredictionCache hit-rate monitoring in ops dashboard
3. Validation gate: Kronos factor contribution vs benchmark

## P2 — Agents integration depth

1. Surface per-agent cards in portal from `agents` envelope field
2. Persist agent runs to audit store (opt-in)
3. A/B/C/D rating alignment between AgentsOS narrative and ScoringOS formula

## P3 — Performance

1. Universe snapshot pre-warm on market close
2. Advisory p95 < 3s cached, < 15s cold (per v2.2 SLA)
3. ComputeOS DAG parallelization for cross-sectional factors

## P4 — Compliance

1. Expand `source_registry.yaml` with legal notes per field
2. Automated DataTruthOS gate in CI for all new data loaders
3. User-facing data lineage export (PDF appendix)
