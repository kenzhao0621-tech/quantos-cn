# 03 — Validation Semantics Repair Report

**Date**: 2026-06-16

## Problem

Failed live fetch followed by `validate-latest-snapshot` could exit 0 on stale `manual_snapshot` (12 rows).

## Fix

- Every `fetch-market-snapshot` emits a unique `run_id`
- Manifests and normalized JSON are run-bound under `data/manifests/{run_id}/`
- `validate-latest-snapshot --run-id` loads only that run; no older snapshot fallback
- Freshness flags with explicit exit codes (0/2–9)

## Verified

- Run-bound Sina validation passes with `--require-live`
- Missing run_id returns exit 2
- Stale manual snapshot cannot satisfy a different run_id

**Status**: REPAIRED
