"""ScreenerService — practical multi-factor A-share ranking on the canonical store.

Reads the canonical DuckDB daily_bars and ranks the investable universe with a
transparent, modern multi-factor composite (momentum + trend + liquidity, with a
volatility penalty). It applies A-share-aware tradability filters (liquidity floor,
exclude limit-up names you cannot buy into) so the output is genuinely actionable.

This is research output only — it never places orders.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[2]
WAREHOUSE = ROOT / "data" / "warehouse" / "quant.duckdb"
_LIVE_CACHE: tuple[float, dict[str, dict[str, Any]], dict[str, Any]] | None = None

# Preset factor weightings. Sum need not be 1; scores are z-normalised.
PRESETS: dict[str, dict[str, float]] = {
    "momentum": {"ret_20": 0.35, "ret_60": 0.35, "trend": 0.20, "vol_penalty": 0.10},
    "trend": {"ret_20": 0.20, "ret_60": 0.25, "trend": 0.45, "vol_penalty": 0.10},
    "balanced": {"ret_20": 0.30, "ret_60": 0.25, "trend": 0.25, "vol_penalty": 0.20},
    "low_vol": {"ret_20": 0.20, "ret_60": 0.20, "trend": 0.20, "vol_penalty": 0.40},
}


@dataclass(frozen=True)
class Candidate:
    rank: int
    symbol: str
    last_close: float
    last_pct: float
    ret_20: float
    ret_60: float
    trend: float
    vol_20: float
    avg_amount: float
    score: float
    spark: list[float] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    sector: str = ""
    live_price: float | None = None
    live_pct: float | None = None
    live_amount: float | None = None
    pe: float | None = None
    pb: float | None = None
    dividend_yield: float | None = None
    market_cap: float | None = None
    disclosure_flag: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "symbol": self.symbol,
            "last_close": round(self.last_close, 2),
            "last_pct": round(self.last_pct, 2),
            "ret_20": round(self.ret_20 * 100, 2),
            "ret_60": round(self.ret_60 * 100, 2),
            "trend": round(self.trend * 100, 2),
            "vol_20": round(self.vol_20, 2),
            "avg_amount": round(self.avg_amount, 0),
            "score": round(self.score, 3),
            "spark": [round(x, 2) for x in self.spark],
            "reasons": self.reasons,
            "sector": self.sector,
            "live_price": round(self.live_price, 2) if self.live_price is not None else None,
            "live_pct": round(self.live_pct, 2) if self.live_pct is not None else None,
            "live_amount": round(self.live_amount, 0) if self.live_amount is not None else None,
            "pe": round(self.pe, 2) if self.pe is not None else None,
            "pb": round(self.pb, 2) if self.pb is not None else None,
            "dividend_yield": round(self.dividend_yield, 2) if self.dividend_yield is not None else None,
            "market_cap": round(self.market_cap, 0) if self.market_cap is not None else None,
            "disclosure_flag": self.disclosure_flag,
        }


@dataclass
class ScreenResult:
    as_of_date: Optional[str]
    preset: str
    universe_size: int
    candidates: list[Candidate]
    mode: str = "eod"
    live_status: dict[str, Any] = field(default_factory=dict)
    blocked: bool = False
    blocker_reason: str = ""
    diversity_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        from quant.scoring.enrichment import enrich_candidate
        from quant.portfolio.allocator import allocate_top_k

        validation_status = _cached_validation_status()
        regime = _cached_regime_label()
        enriched = [
            enrich_candidate(
                c.to_dict(),
                rank=c.rank,
                preset=self.preset,
                as_of_date=self.as_of_date or "",
                validation_status=validation_status,
                regime=regime,
            )
            for c in self.candidates
        ]
        allocation = allocate_top_k(enriched, capital_cny=5000.0)
        return {
            "as_of_date": self.as_of_date,
            "factor_as_of_date": self.as_of_date,
            "data_cutoff": self.as_of_date,
            "live_retrieved_at": self.live_status.get("retrieved_at"),
            "live_freshness": self.live_status.get("freshness"),
            "live_provider": self.live_status.get("provider"),
            "preset": self.preset,
            "mode": self.mode,
            "model_version": "screener_v2_multi_target_2026-06-17",
            "forecast_horizon": "T+1_close_to_close",
            "universe_size": self.universe_size,
            "candidates": enriched,
            "portfolio_allocation_5000": allocation,
            "live_status": self.live_status,
            "blocked": self.blocked,
            "blocker_reason": self.blocker_reason,
            "validation_status": validation_status.get("verdict", "NOT_RUN"),
            "diversity_notes": self.diversity_notes,
        }


class ScreenerService:
    def __init__(self, warehouse: Path | None = None) -> None:
        self.warehouse = warehouse or WAREHOUSE

    def screen(
        self,
        *,
        preset: str = "balanced",
        top_n: int = 25,
        min_amount_cny: float = 5e7,
        exclude_st: bool = True,
        as_of_date: str | None = None,
        mode: str = "eod",
        preferred_sectors: list[str] | None = None,
        excluded_sectors: list[str] | None = None,
    ) -> ScreenResult:
        weights = PRESETS.get(preset, PRESETS["balanced"])
        if not self.warehouse.exists():
            return ScreenResult(None, preset, 0, [], blocked=True,
                                blocker_reason="数据仓库不存在 — 请先运行「更新数据」")
        try:
            import duckdb
            import statistics
        except Exception as exc:  # pragma: no cover
            return ScreenResult(None, preset, 0, [], blocked=True, blocker_reason=str(exc)[:120])

        preferred = _expand_sector_terms(preferred_sectors or [])
        excluded = _expand_sector_terms(excluded_sectors or [])
        sector_map = _load_sector_map()
        fundamental_map = _load_fundamental_map()
        disclosure_map = _load_disclosure_map()
        live_map: dict[str, dict[str, Any]] = {}
        live_status: dict[str, Any] = {"mode": mode, "used": False}
        if mode.lower() in ("live", "realtime", "intraday"):
            live_map, live_status = _load_or_fetch_live_map()

        con = duckdb.connect(str(self.warehouse), read_only=True)
        if as_of_date:
            as_of = con.execute(
                "SELECT max(trade_date) FROM daily_bars WHERE trade_date <= ?",
                [as_of_date],
            ).fetchone()[0]
        else:
            as_of = con.execute("SELECT max(trade_date) FROM daily_bars").fetchone()[0]
        as_of_str = str(as_of) if as_of else None
        if not as_of:
            con.close()
            return ScreenResult(None, preset, 0, [], blocked=True,
                                blocker_reason="没有可用交易日数据")

        rows = con.execute(
            """
            WITH recent AS (
                SELECT ts_code, trade_date, close, pct_chg, amount,
                       row_number() OVER (PARTITION BY ts_code ORDER BY trade_date DESC) AS rn
                FROM daily_bars
                WHERE trade_date <= ?
                  AND trade_date >= (?::DATE - INTERVAL 140 DAY)
            )
            SELECT ts_code,
                   max(CASE WHEN rn = 1 THEN close END)   AS last_close,
                   max(CASE WHEN rn = 1 THEN pct_chg END) AS last_pct,
                   max(CASE WHEN rn = 21 THEN close END)  AS close_20,
                   max(CASE WHEN rn = 61 THEN close END)  AS close_60,
                   avg(CASE WHEN rn <= 20 THEN close END) AS ma20,
                   avg(CASE WHEN rn <= 20 THEN amount END) AS avg_amt20,
                   stddev_samp(CASE WHEN rn <= 20 THEN pct_chg END) AS vol20,
                   count(*) AS n
            FROM recent
            GROUP BY ts_code
            HAVING n >= 61
            """,
            [as_of_str, as_of_str],
        ).fetchall()

        raw: list[dict[str, Any]] = []
        for ts_code, last_close, last_pct, c20, c60, ma20, avg_amt, vol20, n in rows:
            if not (last_close and c20 and c60 and ma20):
                continue
            # Tushare stores `amount` in 千元 (thousands of yuan); convert to yuan.
            avg_amount_yuan = float(avg_amt) * 1000.0 if avg_amt is not None else 0.0
            if avg_amount_yuan < min_amount_cny:
                continue
            if last_pct is not None and last_pct >= 9.8:  # limit-up: can't enter
                continue
            if exclude_st and not _is_main_board(ts_code):
                continue
            sector = sector_map.get(ts_code, "")
            if preferred and not _sector_matches(sector, preferred):
                continue
            if excluded and _sector_matches(sector, excluded):
                continue
            row = {
                "symbol": ts_code,
                "last_close": float(last_close),
                "last_pct": float(last_pct or 0.0),
                "ret_20": float(last_close) / float(c20) - 1.0,
                "ret_60": float(last_close) / float(c60) - 1.0,
                "trend": float(last_close) / float(ma20) - 1.0,
                "vol_20": float(vol20 or 0.0),
                "avg_amount": avg_amount_yuan,
                "sector": sector,
            }
            fund = fundamental_map.get(ts_code, {})
            if fund:
                row.update({
                    "pe": _to_float(fund.get("pe")),
                    "pb": _to_float(fund.get("pb")),
                    "dividend_yield": _to_float(fund.get("dv_ttm")),
                    "market_cap": _to_float(fund.get("total_mv")),
                })
            disc = disclosure_map.get(ts_code)
            if disc:
                row["disclosure_flag"] = disc.get("severity") or disc.get("category") or "DISCLOSURE"
            live = live_map.get(ts_code)
            if live:
                row.update({
                    "live_price": _to_float(live.get("price")),
                    "live_pct": _to_float(live.get("change_pct")),
                    "live_amount": _to_float(live.get("amount")),
                })
            raw.append(row)

        universe = len(raw)
        if universe == 0:
            con.close()
            return ScreenResult(as_of_str, preset, 0, [], blocked=True,
                                blocker_reason="无满足流动性条件的标的")

        def zscores(key: str) -> dict[str, float]:
            vals = [r[key] for r in raw]
            mean = statistics.fmean(vals)
            sd = statistics.pstdev(vals) or 1.0
            return {r["symbol"]: (r[key] - mean) / sd for r in raw}

        z = {k: zscores(k) for k in ("ret_20", "ret_60", "trend", "vol_20")}
        if any(r.get("live_pct") is not None for r in raw):
            z["live_pct"] = zscores_nullable(raw, "live_pct")
            z["live_amount"] = zscores_nullable(raw, "live_amount")
        for optional in ("pe", "pb", "dividend_yield", "market_cap"):
            if any(r.get(optional) is not None for r in raw):
                z[optional] = zscores_nullable(raw, optional)
        for r in raw:
            sym = r["symbol"]
            base_score = (
                weights["ret_20"] * z["ret_20"][sym]
                + weights["ret_60"] * z["ret_60"][sym]
                + weights["trend"] * z["trend"][sym]
                - weights["vol_penalty"] * z["vol_20"][sym]
            )
            live_score = 0.0
            if "live_pct" in z and r.get("live_pct") is not None:
                if preset == "momentum":
                    live_score += 1.15 * z["live_pct"].get(sym, 0.0) + 0.35 * z["live_amount"].get(sym, 0.0)
                elif preset == "low_vol":
                    live_score += 0.35 * z["live_pct"].get(sym, 0.0)
                else:
                    live_score += 0.85 * z["live_pct"].get(sym, 0.0) + 0.25 * z["live_amount"].get(sym, 0.0)
                # Do not chase hard limit-up names in live mode.
                if float(r.get("live_pct") or 0) >= 9.8:
                    live_score -= 3.0
            sector_bonus = 0.0
            if preferred and _sector_matches(r.get("sector", ""), preferred):
                sector_bonus = 1.2
            quality_score = 0.0
            if "pe" in z and r.get("pe") is not None and float(r["pe"]) > 0:
                quality_score += -0.16 * z["pe"].get(sym, 0.0)
            if "pb" in z and r.get("pb") is not None and float(r["pb"]) > 0:
                quality_score += -0.12 * z["pb"].get(sym, 0.0)
            if "dividend_yield" in z and r.get("dividend_yield") is not None:
                quality_score += 0.10 * z["dividend_yield"].get(sym, 0.0)
            disclosure_penalty = -1.0 if str(r.get("disclosure_flag", "")).upper() in {"HIGH", "MEDIUM"} else 0.0
            if mode.lower() in ("live", "realtime", "intraday") and "live_pct" in z:
                r["score"] = 0.45 * base_score + live_score + sector_bonus + quality_score + disclosure_penalty
            else:
                r["score"] = base_score + sector_bonus + quality_score + disclosure_penalty

        raw.sort(key=lambda r: r["score"], reverse=True)
        from quant.screener.diversity import apply_diversity_constraints

        top, diversity_notes = apply_diversity_constraints(raw, top_n=max(1, top_n))
        if not top:
            top = raw[: max(1, top_n)]

        # sparkline (last ~30 closes) for the shortlist only
        spark_map: dict[str, list[float]] = {}
        if top:
            syms = [r["symbol"] for r in top]
            placeholders = ",".join(["?"] * len(syms))
            srows = con.execute(
                f"""
                SELECT ts_code, close FROM (
                    SELECT ts_code, trade_date, close,
                           row_number() OVER (PARTITION BY ts_code ORDER BY trade_date DESC) AS rn
                    FROM daily_bars WHERE ts_code IN ({placeholders})
                ) WHERE rn <= 30 ORDER BY ts_code, trade_date
                """,
                syms,
            ).fetchall()
            for ts_code, close in srows:
                spark_map.setdefault(ts_code, []).append(float(close))
        con.close()

        candidates = [
            Candidate(
                rank=i + 1,
                symbol=r["symbol"],
                last_close=r["last_close"],
                last_pct=r["last_pct"],
                ret_20=r["ret_20"],
                ret_60=r["ret_60"],
                trend=r["trend"],
                vol_20=r["vol_20"],
                avg_amount=r["avg_amount"],
                score=r["score"],
                spark=spark_map.get(r["symbol"], []),
                reasons=_candidate_reasons(r),
                sector=r.get("sector", ""),
                live_price=r.get("live_price"),
                live_pct=r.get("live_pct"),
                live_amount=r.get("live_amount"),
                pe=r.get("pe"),
                pb=r.get("pb"),
                dividend_yield=r.get("dividend_yield"),
                market_cap=r.get("market_cap"),
                disclosure_flag=r.get("disclosure_flag", ""),
            )
            for i, r in enumerate(top)
        ]
        return ScreenResult(
            as_of_str, preset, universe, candidates, mode=mode, live_status=live_status,
            diversity_notes=diversity_notes,
        )

    def dossier(
        self,
        symbol: str,
        *,
        preset: str = "balanced",
        as_of_date: str | None = None,
        mode: str = "eod",
        preferred_sectors: list[str] | None = None,
        excluded_sectors: list[str] | None = None,
    ) -> dict[str, Any]:
        """Return a user-readable explanation for one stock candidate."""
        result = self.screen(
            preset=preset,
            top_n=500,
            as_of_date=as_of_date,
            mode=mode,
            preferred_sectors=preferred_sectors,
            excluded_sectors=excluded_sectors,
        )
        candidate = next((c for c in result.candidates if c.symbol == symbol), None)
        import duckdb

        con = duckdb.connect(str(self.warehouse), read_only=True)
        date_filter = "AND trade_date <= ?" if result.as_of_date else ""
        params = [symbol] + ([result.as_of_date] if result.as_of_date else [])
        hist = con.execute(
            f"""
            SELECT trade_date, open, high, low, close, pct_chg, amount
            FROM daily_bars
            WHERE ts_code = ? {date_filter}
            ORDER BY trade_date DESC
            LIMIT 80
            """,
            params,
        ).fetchall()
        con.close()
        history = [
            {
                "trade_date": str(d),
                "open": round(float(o), 2),
                "high": round(float(h), 2),
                "low": round(float(l), 2),
                "close": round(float(c), 2),
                "pct_chg": round(float(p or 0), 2),
                "amount_cny": round(float(a or 0) * 1000.0, 0),
            }
            for d, o, h, l, c, p, a in reversed(hist)
        ]
        return {
            "symbol": symbol,
            "as_of_date": result.as_of_date,
            "rank": candidate.rank if candidate else None,
            "candidate": candidate.to_dict() if candidate else None,
            "plain_language": _plain_language(candidate),
            "institutional_report": _institutional_report(candidate, history),
            "risk_notes": [
                "仅研究/模拟交易，不构成投资建议",
                "A股 T+1：买入当日不可卖出",
                "涨停附近不追入，跌破止损/趋势无效必须退出模拟计划",
            ],
            "history": history,
        }

    def prove_next_day(self, *, preset: str = "balanced", top_n: int = 25) -> dict[str, Any]:
        """Validate previous trade day's picks against the next available session."""
        import duckdb
        import statistics

        con = duckdb.connect(str(self.warehouse), read_only=True)
        dates = [str(x[0]) for x in con.execute("SELECT DISTINCT trade_date FROM daily_bars ORDER BY trade_date").fetchall()]
        if len(dates) < 62:
            con.close()
            return {"blocked": True, "blocker_reason": "历史交易日不足，无法做 T+1 验证"}
        signal_date, proof_date = dates[-2], dates[-1]
        screen = self.screen(preset=preset, top_n=top_n, as_of_date=signal_date)
        symbols = [c.symbol for c in screen.candidates]
        if not symbols:
            con.close()
            return {"blocked": True, "blocker_reason": "上一交易日无候选", "signal_date": signal_date, "proof_date": proof_date}

        placeholders = ",".join(["?"] * len(symbols))
        rows = con.execute(
            f"""
            SELECT s.ts_code, s.close AS signal_close,
                   p.open AS proof_open, p.high AS proof_high, p.low AS proof_low,
                   p.close AS proof_close, p.pct_chg AS proof_pct
            FROM daily_bars s
            JOIN daily_bars p ON p.ts_code = s.ts_code
            WHERE s.trade_date = ? AND p.trade_date = ? AND s.ts_code IN ({placeholders})
            """,
            [signal_date, proof_date, *symbols],
        ).fetchall()
        bench_rows = con.execute(
            """
            SELECT ((p.close / s.close) - 1.0) * 100 AS ret
            FROM daily_bars s
            JOIN daily_bars p ON p.ts_code = s.ts_code
            WHERE s.trade_date = ? AND p.trade_date = ? AND s.close > 0
            """,
            [signal_date, proof_date],
        ).fetchall()
        con.close()

        candidate_by_symbol = {c.symbol: c for c in screen.candidates}
        ret_values = [float(x[0]) for x in bench_rows if x[0] is not None]
        benchmark_mean = statistics.fmean(ret_values) if ret_values else 0.0
        benchmark_median = statistics.median(ret_values) if ret_values else 0.0
        proofs: list[dict[str, Any]] = []
        for symbol, s_close, p_open, p_high, p_low, p_close, p_pct in rows:
            cand = candidate_by_symbol[symbol]
            next_ret = ((float(p_close) / float(s_close)) - 1.0) * 100.0
            gap_ret = ((float(p_open) / float(s_close)) - 1.0) * 100.0
            mfe = ((float(p_high) / float(s_close)) - 1.0) * 100.0
            mae = ((float(p_low) / float(s_close)) - 1.0) * 100.0
            passed = next_ret > benchmark_median and next_ret > 0
            proofs.append({
                "rank": cand.rank,
                "symbol": symbol,
                "signal_close": round(float(s_close), 2),
                "proof_open": round(float(p_open), 2),
                "proof_close": round(float(p_close), 2),
                "next_day_return": round(next_ret, 2),
                "gap_return": round(gap_ret, 2),
                "mfe": round(mfe, 2),
                "mae": round(mae, 2),
                "benchmark_median": round(benchmark_median, 2),
                "outperformance": round(next_ret - benchmark_median, 2),
                "passed": passed,
                "diagnosis": _proof_diagnosis(next_ret, benchmark_median, gap_ret, mae),
            })
        avg = statistics.fmean([p["next_day_return"] for p in proofs]) if proofs else 0.0
        hit_rate = sum(1 for p in proofs if p["next_day_return"] > 0) / max(len(proofs), 1)
        win_rate = sum(1 for p in proofs if p["outperformance"] > 0) / max(len(proofs), 1)
        verdict = "PASS" if avg > benchmark_median and win_rate >= 0.5 else "NEEDS_REVIEW"
        return {
            "blocked": False,
            "signal_date": signal_date,
            "proof_date": proof_date,
            "preset": preset,
            "top_n": top_n,
            "candidate_count": len(proofs),
            "avg_return": round(avg, 2),
            "hit_rate": round(hit_rate * 100, 1),
            "win_rate_vs_median": round(win_rate * 100, 1),
            "benchmark_mean": round(benchmark_mean, 2),
            "benchmark_median": round(benchmark_median, 2),
            "verdict": verdict,
            "what_to_adjust": _adjustment_notes(proofs, benchmark_median),
            "proofs": proofs,
        }


def _is_main_board(ts_code: str) -> bool:
    code = ts_code.split(".")[0]
    # Keep SH main (60), SZ main (00), ChiNext (30), STAR (688). Drop BSE (8/4) etc.
    return code.startswith(("60", "00", "30", "688"))


def zscores_nullable(rows: list[dict[str, Any]], key: str) -> dict[str, float]:
    import statistics

    vals = [float(r[key]) for r in rows if r.get(key) is not None]
    if not vals:
        return {}
    mean = statistics.fmean(vals)
    sd = statistics.pstdev(vals) or 1.0
    return {
        r["symbol"]: (float(r[key]) - mean) / sd
        for r in rows
        if r.get(key) is not None
    }


def _to_float(val: Any) -> float | None:
    try:
        if val is None:
            return None
        f = float(val)
        if f != f:
            return None
        return f
    except (TypeError, ValueError):
        return None


def _load_sector_map() -> dict[str, str]:
    import json

    path = ROOT / "data" / "sectors" / "sector_boards_tushare.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for row in data.get("rows", []):
        code = str(row.get("code", "")).zfill(6)
        sector = str(row.get("sector_name") or row.get("sector_code") or "")
        if not code or not sector:
            continue
        suffixes = ["SH"] if code.startswith("6") else ["SZ"]
        if code.startswith(("4", "8", "9")):
            suffixes = ["BJ"]
        for suf in suffixes:
            out[f"{code}.{suf}"] = sector
    return out


def _load_fundamental_map() -> dict[str, dict[str, Any]]:
    import json

    path = ROOT / "data" / "fundamentals" / "fundamentals_tushare.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        str(row.get("ts_code", "")): row
        for row in data.get("rows", [])
        if row.get("ts_code")
    }


def _load_disclosure_map() -> dict[str, dict[str, Any]]:
    import json

    path = ROOT / "data" / "disclosures" / "disclosures_cninfo_official.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, dict[str, Any]] = {}
    for row in data.get("rows", []):
        code = str(row.get("stock_code", "")).zfill(6)
        exchange = str(row.get("exchange", "")).upper()
        suffix = "SH" if exchange.startswith("SSE") or code.startswith("6") else "SZ"
        out[f"{code}.{suffix}"] = row
    return out


def _live_symbol(row: dict[str, Any]) -> str:
    import re

    raw = str(row.get("code", "")).strip()
    digits = "".join(re.findall(r"\d+", raw))
    code = digits[-6:].zfill(6) if digits else raw.zfill(6)
    exchange = str(row.get("exchange") or row.get("market") or "").upper()
    if raw.lower().startswith("sh"):
        exchange = "SH"
    elif raw.lower().startswith("sz"):
        exchange = "SZ"
    elif raw.lower().startswith("bj"):
        exchange = "BJ"
    if exchange not in ("SH", "SZ", "BJ"):
        exchange = "SH" if code.startswith("6") else "SZ"
    return f"{code}.{exchange}"


def _load_or_fetch_live_map() -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    import json
    import time

    global _LIVE_CACHE
    now = time.time()
    if _LIVE_CACHE and now - _LIVE_CACHE[0] < 60:
        live_map = _LIVE_CACHE[1]
        status = dict(_LIVE_CACHE[2])
        status["source"] = f"{status.get('source', 'fabric')}:cache"
        return live_map, status

    status: dict[str, Any] = {"mode": "live", "used": False, "source": "none"}
    live_path = ROOT / "data" / "gateway" / "live_snapshot.json"
    rows: list[dict[str, Any]] = []
    if live_path.exists():
        data = json.loads(live_path.read_text(encoding="utf-8"))
        # The persisted scheduler snapshot stores metadata only; portal live API
        # stores top lists. If full rows are absent, fetch fresh below.
        rows = data.get("rows", []) or []
        status.update({
            "source": "persisted",
            "retrieved_at": data.get("retrieved_at"),
            "provider": data.get("provider"),
            "row_count": data.get("row_count"),
        })
    if not rows:
        try:
            from quant.application.live_market_service import fetch_live_snapshot

            snap = fetch_live_snapshot(require_live=False)
            rows = snap.get("rows", []) or []
            # fetch_live_snapshot intentionally returns top lists, not full rows.
            # For live scoring we need the full fabric payload, so fall through to
            # direct application helper if rows are missing.
            status.update(snap)
        except Exception as exc:
            status.update({"error": str(exc)[:160]})
    if not rows:
        try:
            from quant.market_data_fabric import MarketDataFabric

            fetched = MarketDataFabric().fetch("spot_quotes", live_only=True, require_live=False, min_rows=1000)
            if fetched.ok and fetched.result:
                payload = fetched.result.payload or {}
                rows = payload.get("rows", []) or []
                status = {
                    "mode": "live",
                    "used": True,
                    "source": "fabric",
                    "provider": fetched.result.provider,
                    "retrieved_at": fetched.result.retrieved_at,
                    "freshness": payload.get("freshness") or fetched.result.freshness,
                    "row_count": len(rows),
                }
            else:
                status.update({"blocked": True, "reason": fetched.selection_reason})
        except Exception as exc:
            status.update({"blocked": True, "error": str(exc)[:160]})
    live_map = {_live_symbol(row): row for row in rows if row.get("code")}
    status["used"] = bool(live_map)
    status["row_count"] = len(live_map) or status.get("row_count", 0)
    if live_map:
        _LIVE_CACHE = (now, live_map, status)
    return live_map, status


SECTOR_ALIASES: dict[str, list[str]] = {
    "房地产": ["房地产", "地产", "房子", "房产", "物业", "开发", "住宅", "全国地产", "区域地产", "园区开发"],
    "银行": ["银行", "股份制银行", "城商行", "农商行"],
    "证券": ["证券", "券商", "投行", "经纪", "证券公司"],
    "保险": ["保险", "寿险", "财险"],
    "半导体": ["半导体", "芯片", "集成电路", "晶圆", "封测", "光刻", "存储", "元器件"],
    "人工智能": ["人工智能", "AI", "算力", "数据中心", "服务器", "云计算", "软件服务", "互联网"],
    "新能源": ["新能源", "光伏", "风电", "储能", "电池", "锂电", "新能源车", "汽车类"],
    "医药": ["医药", "生物", "医疗", "制药", "中成药", "化学制药", "医疗保健"],
    "消费": ["消费", "食品", "饮料", "白酒", "家电", "商贸", "旅游", "酒店餐饮"],
    "军工": ["军工", "航空", "航天", "船舶", "国防"],
    "有色": ["有色", "黄金", "铜", "铝", "稀土", "小金属"],
}


def _expand_sector_terms(terms: list[str]) -> list[str]:
    expanded: list[str] = []
    for raw in terms:
        term = str(raw).strip()
        if not term:
            continue
        expanded.append(term)
        lower = term.lower()
        for key, aliases in SECTOR_ALIASES.items():
            if lower == key.lower() or any(lower == a.lower() for a in aliases):
                expanded.extend(aliases)
            elif any(lower in a.lower() or a.lower() in lower for a in aliases):
                expanded.extend(aliases)
    # stable de-dup preserving order
    seen: set[str] = set()
    out: list[str] = []
    for x in expanded:
        k = x.lower()
        if k not in seen:
            seen.add(k)
            out.append(x)
    return out


def _sector_matches(sector: str, terms: list[str]) -> bool:
    sector_norm = str(sector or "").strip().lower()
    if not sector_norm:
        return False
    return any(t.lower() in sector_norm or sector_norm in t.lower() for t in terms)


def _candidate_reasons(row: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if row.get("sector"):
        reasons.append(f"所属板块：{row['sector']}")
    if row.get("live_pct") is not None:
        reasons.append(f"实时涨跌幅：{float(row['live_pct']):.2f}%")
    if row.get("live_amount") is not None and float(row["live_amount"]) > 0:
        reasons.append(f"实时成交额：{float(row['live_amount']) / 1e8:.2f} 亿")
    if row.get("pe") is not None:
        reasons.append(f"估值PE：{float(row['pe']):.2f}")
    if row.get("pb") is not None:
        reasons.append(f"PB：{float(row['pb']):.2f}")
    if row.get("dividend_yield") is not None and float(row["dividend_yield"]) > 0:
        reasons.append(f"股息率：{float(row['dividend_yield']):.2f}%")
    if row.get("disclosure_flag"):
        reasons.append(f"公告提示：{row['disclosure_flag']}")
    if row["ret_20"] > 0.2:
        reasons.append(f"20日动量强：{row['ret_20'] * 100:.1f}%")
    if row["ret_60"] > 0.5:
        reasons.append(f"60日趋势强：{row['ret_60'] * 100:.1f}%")
    if row["trend"] > 0.1:
        reasons.append(f"价格高于20日均线：{row['trend'] * 100:.1f}%")
    if row["avg_amount"] > 3e8:
        reasons.append(f"流动性充足：日均成交额 {row['avg_amount'] / 1e8:.1f} 亿")
    if row["vol_20"] > 7:
        reasons.append(f"波动较高：20日波动 {row['vol_20']:.1f}，仓位需降低")
    if not reasons:
        reasons.append("综合评分靠前，但单项优势不极端")
    return reasons[:5]


def _plain_language(candidate: Candidate | None) -> str:
    if not candidate:
        return "该股票当前不在前100候选内，暂不建议纳入模拟组合。"
    parts = [
        f"{candidate.symbol} 当前排名第 {candidate.rank}，综合分 {candidate.score:.2f}。",
        "主要依据：" + "；".join(candidate.reasons),
    ]
    if candidate.last_pct >= 9.5:
        parts.append("注意：接近涨停，不适合追入。")
    if candidate.vol_20 > 7:
        parts.append("风险：波动偏高，建议低仓位或等待回踩。")
    else:
        parts.append("风险：趋势股仍需设置止损，不应满仓。")
    return " ".join(parts)


def _institutional_report(candidate: Candidate | None, history: list[dict[str, Any]]) -> dict[str, Any]:
    """Institutional-style factor report without fabricating unavailable data."""
    if not candidate:
        return {
            "overall": "NOT_IN_TOP_UNIVERSE",
            "methodology": "多因子排名：动量、趋势、流动性、波动风险、执行约束。",
            "factors": [],
        }
    closes = [float(x["close"]) for x in history if x.get("close")]
    drawdown = 0.0
    if closes:
        peak = closes[0]
        max_dd = 0.0
        for v in closes:
            peak = max(peak, v)
            max_dd = min(max_dd, (v / peak - 1.0) * 100)
        drawdown = max_dd
    factors = [
        {
            "name": "价格动量",
            "weight": 0.25,
            "score": _clip_score(candidate.ret_20 / 80.0 + candidate.ret_60 / 240.0),
            "evidence": f"20日 {candidate.ret_20:.2f}% / 60日 {candidate.ret_60:.2f}%",
        },
        {
            "name": "趋势质量",
            "weight": 0.20,
            "score": _clip_score(candidate.trend / 40.0),
            "evidence": f"相对20日均线 {candidate.trend:.2f}%",
        },
        {
            "name": "流动性/容量",
            "weight": 0.18,
            "score": _clip_score((candidate.avg_amount / 1e8) / 20.0),
            "evidence": f"20日日均成交额 {candidate.avg_amount / 1e8:.2f} 亿",
        },
        {
            "name": "波动和回撤风险",
            "weight": 0.17,
            "score": _clip_score(1.0 - candidate.vol_20 / 12.0),
            "evidence": f"20日波动 {candidate.vol_20:.2f}，80日最大回撤 {drawdown:.2f}%",
        },
        {
            "name": "交易可执行性",
            "weight": 0.10,
            "score": 0.2 if candidate.last_pct >= 9.5 else 0.8,
            "evidence": "接近涨停则不可追入；A股一手100股、T+1。",
        },
        {
            "name": "基本面/公告事件",
            "weight": 0.10,
            "score": _fundamental_component(candidate),
            "evidence": _fundamental_evidence(candidate),
        },
    ]
    total = sum(f["weight"] * f["score"] for f in factors)
    return {
        "overall": "WATCHLIST" if total >= 0.55 else "REVIEW_ONLY",
        "weighted_score": round(total * 100, 1),
        "methodology": "机构常用框架：收益动量、趋势持续性、流动性容量、波动/回撤风险、交易约束、基本面/事件。缺失数据不编造，只标注待接入。",
        "factors": factors,
        "decision_rule": "仅当实时数据未失真、未涨停追高、组合仓位满足用户风险偏好时，才允许进入 Paper/Shadow 研究路径。",
    }


def _clip_score(x: float) -> float:
    return round(max(0.0, min(1.0, x)), 3)


def _fundamental_component(candidate: Candidate) -> float:
    score = 0.5
    if candidate.pe is not None and candidate.pe > 0:
        if candidate.pe < 15:
            score += 0.18
        elif candidate.pe > 80:
            score -= 0.18
    if candidate.pb is not None and candidate.pb > 0:
        if candidate.pb < 2:
            score += 0.12
        elif candidate.pb > 8:
            score -= 0.12
    if candidate.dividend_yield is not None and candidate.dividend_yield > 2:
        score += 0.10
    if candidate.disclosure_flag.upper() in {"HIGH", "MEDIUM"}:
        score -= 0.25
    return _clip_score(score)


def _fundamental_evidence(candidate: Candidate) -> str:
    parts: list[str] = []
    if candidate.pe is not None:
        parts.append(f"PE {candidate.pe:.2f}")
    if candidate.pb is not None:
        parts.append(f"PB {candidate.pb:.2f}")
    if candidate.dividend_yield is not None:
        parts.append(f"股息率 {candidate.dividend_yield:.2f}%")
    if candidate.disclosure_flag:
        parts.append(f"公告 {candidate.disclosure_flag}")
    return "；".join(parts) if parts else "暂无可验证基本面/公告数据"


def _proof_diagnosis(next_ret: float, benchmark_median: float, gap_ret: float, mae: float) -> str:
    if next_ret > benchmark_median and next_ret > 0:
        return "达标：次日收盘收益为正且跑赢市场中位数。"
    if gap_ret > 3 and next_ret < gap_ret:
        return "未达标：高开后回落，说明追高风险较大，应加入开盘冲高过滤。"
    if mae < -5:
        return "未达标：盘中最大回撤过深，应提高波动率惩罚或降低仓位。"
    if next_ret < 0 and benchmark_median > 0:
        return "未达标：个股弱于市场，需增加行业/事件/资金流过滤。"
    return "未达标：收益未跑赢基准，需复核因子权重。"


def _adjustment_notes(proofs: list[dict[str, Any]], benchmark_median: float) -> list[str]:
    if not proofs:
        return ["没有可验证候选。"]
    notes: list[str] = []
    avg_mae = sum(p["mae"] for p in proofs) / len(proofs)
    gap_fades = sum(1 for p in proofs if p["gap_return"] > 3 and p["next_day_return"] < p["gap_return"])
    negatives = sum(1 for p in proofs if p["next_day_return"] < 0)
    under = sum(1 for p in proofs if p["next_day_return"] <= benchmark_median)
    if negatives / len(proofs) > 0.4:
        notes.append("负收益比例偏高：增加大盘/板块 regime 过滤，不在弱市强行选股。")
    if under / len(proofs) > 0.5:
        notes.append("跑输市场中位数过多：提高因子多样性，不能只看动量。")
    if gap_fades / len(proofs) > 0.25:
        notes.append("高开回落较多：加入开盘追高保护，避免隔夜后追入。")
    if avg_mae < -4:
        notes.append("盘中回撤偏大：提高波动率惩罚并降低单票权重。")
    if not notes:
        notes.append("当前验证基本可接受：继续累计样本，避免因一天结果过度调参。")
    return notes


_service: Optional[ScreenerService] = None


def _cached_validation_status() -> dict[str, Any]:
    path = ROOT / "artifacts" / "model_validation.json"
    if path.exists():
        try:
            import json
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"verdict": "NOT_RUN", "purged_kfold_passed": None}


def _cached_regime_label() -> dict[str, Any]:
    try:
        from tools.china_quant.regime_v2 import classify_regime_v2
        r = classify_regime_v2()
        return {"label": r.get("regime", "UNKNOWN"), "score": r.get("score")}
    except Exception:
        return {"label": "UNKNOWN"}


def get_screener_service() -> ScreenerService:
    global _service
    if _service is None:
        _service = ScreenerService()
    return _service
