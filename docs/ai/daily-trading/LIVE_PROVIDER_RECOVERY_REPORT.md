# Live Provider Recovery Report

- **Generated**: 2026-06-16T17:55:36 (updated with post-analysis)
- **Branch**: `chore/cursor-operating-system` @ `0dfff67`
- **Venv**: `.venv-china-quant`
- **AKShare**: **1.18.64** (already latest on PyPI; upgrade not required)
- **Recovery success**: **False** (composite pipeline did not pass live spot DQ gate)

## Executive summary

| Outcome | Detail |
|---------|--------|
| Eastmoney endpoints (full + SH/SZ/BJ + index spot) | All **ConnectionError** / `RemoteDisconnected` |
| Sina `stock_zh_a_spot` (direct probe) | **SUCCESS** — 5,527 rows, market date 2026-06-16 |
| Sina direct → Data Quality Gate | **PASS** (min_rows=100, required fields present) |
| Composite `spot_quotes` routing | **FAIL** — `akshare_sina` wrapper calls Eastmoney `get_spot_quotes`, not Sina spot |
| Tencent `stock_zh_a_spot_tx` | **N/A** — function removed/not present in AKShare 1.18.64 |
| Trading calendar | **SUCCESS** — 8,797 dates via `tool_trade_date_hist_sina` |
| Split-market merge | **Not attempted** — all EM segments failed |
| `validate-latest-snapshot` | Exit 0 but validated **stale `manual_snapshot`** (12 rows), not live data |

**Do not treat `validate-latest-snapshot` exit 0 as live recovery success.**

---

## Provider probes (independent)

| Provider | Function | Start | End | Latency ms | Rows | Columns (first 5) | Market date | Success | Exception |
|----------|----------|-------|-----|------------|------|-------------------|-------------|---------|-----------|
| eastmoney_full_market | `ak.stock_zh_a_spot_em` | 17:55:44 | 17:55:51 | 6142 | 0 | — | — | No | ConnectionError |
| eastmoney_shanghai | `ak.stock_sh_a_spot_em` | 17:55:51 | 17:55:56 | 5199 | 0 | — | — | No | ConnectionError |
| eastmoney_shenzhen | `ak.stock_sz_a_spot_em` | 17:55:56 | 17:56:02 | 5718 | 0 | — | — | No | ConnectionError |
| eastmoney_beijing | `ak.stock_bj_a_spot_em` | 17:56:02 | 17:56:07 | 5630 | 0 | — | — | No | ConnectionError |
| sina_spot | `ak.stock_zh_a_spot` | 17:56:07 | 17:56:26 | 19190 | **5527** | 代码,名称,最新价,涨跌额,涨跌幅… | 2026-06-16 | **Yes** | — |
| tencent_spot | `ak.stock_zh_a_spot_tx` | 17:56:26 | 17:56:26 | 0 | 0 | — | — | No | AttributeError |
| index_provider | `ak.stock_zh_index_spot_em` | 17:56:26 | 17:56:32 | 5849 | 0 | — | — | No | ConnectionError |
| trading_calendar | `ak.tool_trade_date_hist_sina` | 17:56:32 | 17:56:32 | 134 | **8797** | trade_date | 2026-12-31 | **Yes** | — |

Sina spot columns (full): `代码`, `名称`, `最新价`, `涨跌额`, `涨跌幅`, `买入`, `卖出`, `昨收`, `今开`, `最高`, `最低`, `成交量`, `成交额`, `时间戳`

---

## Split-market merge

```json
{
  "merged": false,
  "reason": "no successful segments (SH/SZ/BJ all RemoteDisconnected)"
}
```

---

## Data Quality Gate (composite `spot_quotes`)

- **Provider**: none (all akshare routes failed for spot in composite)
- **Passed**: **False**
- **Winner attempts**: `akshare_eastmoney` FAILED, `akshare_split` EMPTY, `akshare_sina` FAILED (uses EM endpoint)

### Sina direct (informational — not wired in composite)

- Function: `ak.stock_zh_a_spot`
- Rows: 5527
- **DQ Gate**: **PASS** (post-recovery verification)
- **Not counted as recovery success** until composite routes Sina spot and persists without manual/fixture data.

---

## Quant CLI results

| Command | Exit | Notes |
|---------|------|-------|
| `python -m quant provider-check --live --provider akshare` | 0 | EM spot/indices/boards FAILED; calendar + security_master SUCCESS |
| `python -m quant fetch-market-snapshot --persist --live-only` | 0 | 2/4 datasets (indices via sina, trading_calendar); **spot_quotes not updated** |
| `python -m quant validate-latest-snapshot --dataset spot_quotes` | 0 | **Misleading** — validated old `manual_snapshot` (12 rows) in data lake |

---

## Root cause

1. **Eastmoney API instability** from this network (consistent `RemoteDisconnected`).
2. **Routing gap**: `akshare_sina` does not call `stock_zh_a_spot` for spot quotes; it delegates to Eastmoney.
3. **Tencent endpoint** absent in AKShare 1.18.64.
4. **Stale lake data**: prior manual import still satisfies validate when live fetch fails.

---

## Recommended next step (focused, not architectural)

Wire `AkshareSinaProvider.fetch(spot_quotes)` to `ak.stock_zh_a_spot()` with schema normalization, then re-run:

```bash
.venv-china-quant/bin/python -m quant fetch-market-snapshot --persist --live-only
.venv-china-quant/bin/python -m quant validate-latest-snapshot --dataset spot_quotes
```

Expected: `row_count` ≥ 5000, `provider` = `akshare_sina`, DQ `passed: true`.
