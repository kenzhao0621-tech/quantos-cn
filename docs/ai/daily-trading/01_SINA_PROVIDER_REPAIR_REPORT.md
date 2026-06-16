# 01 — Sina Provider Repair Report

**Date**: 2026-06-16  
**Branch**: `chore/cursor-operating-system`  
**Pre-change commit**: `0dfff67`

## Root cause

`AkshareSinaProvider` inherited `_AkshareBase.fetch()` for `spot_quotes`, routing to Eastmoney `stock_zh_a_spot_em()` instead of Sina `stock_zh_a_spot()`.

## Repair

| Item | Path |
|------|------|
| Standalone Sina provider | `quant/providers/akshare_family.py` |
| Column normalizer | `quant/providers/sina_normalize.py` |
| Schema | `schemas/akshare_sina_spot_v1.yaml` |

## Live acceptance

| Field | Value |
|-------|-------|
| run_id | `20260616T182312-a29f93a0` |
| provider | `akshare_sina` |
| source_dataset | `stock_zh_a_spot` |
| row_count | 5527 |
| is_live | true |
| quality | passed |
| validate exit | 0 (`--require-live`) |

## Deterministic tests

All Sina-specific tests in `scripts/run-provider-recovery-tests.py` pass.

**Status**: REPAIRED_AND_VERIFIED
