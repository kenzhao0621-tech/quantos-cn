"""ScreenerService — practical multi-factor A-share ranking on the canonical store.

Reads the canonical DuckDB daily_bars and ranks the investable universe with a
transparent, modern multi-factor composite (momentum + trend + liquidity, with a
volatility penalty). It applies A-share-aware tradability filters (liquidity floor,
exclude limit-up names you cannot buy into) so the output is genuinely actionable.

This is research output only — it never places orders.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from quant.screener.names import resolve_name

ROOT = Path(__file__).resolve().parents[2]
WAREHOUSE = ROOT / "data" / "warehouse" / "quant.duckdb"
_LIVE_CACHE: tuple[float, dict[str, dict[str, Any]], dict[str, Any]] | None = None
_UNIVERSE_SCORE_CACHE: tuple[float, str, dict[str, Any]] | None = None
_SCREEN_CACHE: tuple[float, str, "ScreenResult"] | None = None

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
    name: str
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
    alpha_score: float = 0.0
    factor_breakdown: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "symbol": self.symbol,
            "name": self.name,
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
            "alpha_score": round(self.alpha_score, 4),
            "factor_breakdown": self.factor_breakdown,
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
    price_filters: dict[str, Any] = field(default_factory=dict)
    selection_guide: dict[str, Any] = field(default_factory=dict)
    capital_cny: float = 5000.0
    ensemble_meta: dict[str, Any] = field(default_factory=dict)
    agent_overlay: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from quant.scoring.enrichment import enrich_candidate
        from quant.portfolio.unified import build_portfolio_allocation

        validation_status = _cached_validation_status()
        regime = _cached_regime_label()
        cap = float(self.capital_cny or 5000.0)
        try:
            from gateway.preferences import load_preferences

            max_holdings = load_preferences().max_positions
        except Exception:
            max_holdings = 5
        enriched = [
            enrich_candidate(
                c.to_dict(),
                rank=c.rank,
                preset=self.preset,
                as_of_date=self.as_of_date or "",
                capital_cny=cap,
                validation_status=validation_status,
                regime=regime,
            )
            for c in self.candidates
        ]
        allocation = build_portfolio_allocation(
            enriched,
            capital_cny=cap,
            max_holdings=max_holdings,
            regime=regime,
        )
        guide = self.selection_guide or {}
        if not guide:
            from quant.screener.selection_guide import build_selection_guide

            guide = build_selection_guide(
                preset=self.preset,
                mode=self.mode,
                capital_cny=cap,
                price_min_cny=float(self.price_filters.get("price_min_cny") or 0),
                price_max_cny=self.price_filters.get("price_max_cny"),
                enforce_capital_price_ceiling=bool(self.price_filters.get("enforce_capital_price_ceiling", True)),
                universe_size=self.universe_size,
                candidate_count=len(self.candidates),
                validation_status=validation_status.get("verdict", "NOT_RUN"),
                as_of_date=self.as_of_date,
            )
        return {
            "as_of_date": self.as_of_date,
            "factor_as_of_date": self.as_of_date,
            "data_cutoff": self.as_of_date,
            "live_retrieved_at": self.live_status.get("retrieved_at"),
            "live_freshness": self.live_status.get("freshness"),
            "live_provider": self.live_status.get("provider"),
            "preset": self.preset,
            "mode": self.mode,
            "model_version": "screener_v5_ensemble_lgbm_2026-06-17",
            "neutralization": "size_industry",
            "forecast_horizon": "T+1_close_to_close",
            "ensemble_mode": self.ensemble_meta.get("mode", "baseline_fallback"),
            "ml_active": bool(self.ensemble_meta.get("passed")),
            "ml_degraded_reason": self.ensemble_meta.get("reasons") or [],
            "ensemble_weights": self.ensemble_meta.get("weights"),
            "ml_model_id": self.ensemble_meta.get("model_id"),
            "universe_size": self.universe_size,
            "candidates": enriched,
            "portfolio_allocation": allocation,
            "portfolio_allocation_5000": allocation.get("positions") or allocation,
            "live_status": self.live_status,
            "blocked": self.blocked,
            "blocker_reason": self.blocker_reason,
            "validation_status": validation_status.get("verdict", "NOT_RUN"),
            "diversity_notes": self.diversity_notes,
            "price_filters": self.price_filters,
            "selection_guide": guide,
            "capital_cny": cap,
            "agent_overlay": self.agent_overlay,
            "screener_engine": "screener_v6_trading_agents_zh",
        }


class ScreenerService:
    def __init__(self, warehouse: Path | None = None) -> None:
        self.warehouse = warehouse or WAREHOUSE
        self._db = None

    def _connect(self):
        if self._db is None:
            import duckdb
            self._db = duckdb.connect(str(self.warehouse), read_only=True)
        return self._db

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
        price_min_cny: float = 0.0,
        price_max_cny: float | None = None,
        capital_cny: float | None = None,
        enforce_capital_price_ceiling: bool = True,
        fast: bool = False,
    ) -> ScreenResult:
        from quant.screener.selection_guide import build_selection_guide, price_passes, resolve_price_filters
        import time

        global _SCREEN_CACHE
        cache_key = (
            f"{preset}|{top_n}|{min_amount_cny}|{mode}|{as_of_date or ''}|"
            f"{','.join(preferred_sectors or [])}|{','.join(excluded_sectors or [])}|"
            f"{price_min_cny}|{price_max_cny}|{capital_cny}|{enforce_capital_price_ceiling}|{fast}"
        )
        now = time.time()
        if fast and _SCREEN_CACHE and now - _SCREEN_CACHE[0] < 90 and _SCREEN_CACHE[1] == cache_key:
            return _SCREEN_CACHE[2]

        if capital_cny is None:
            try:
                from gateway.preferences import load_preferences

                capital_cny = load_preferences().capital_cny
            except Exception:
                capital_cny = 5000.0
        pmin, user_pmax, eff_max, cap = resolve_price_filters(
            price_min_cny=price_min_cny,
            price_max_cny=price_max_cny,
            capital_cny=capital_cny,
            enforce_capital_price_ceiling=enforce_capital_price_ceiling,
        )
        price_filters = {
            "price_min_cny": pmin,
            "price_max_cny": user_pmax,
            "effective_price_max_cny": eff_max,
            "enforce_capital_price_ceiling": enforce_capital_price_ceiling,
        }
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
        fundamental_map = {} if fast else _load_fundamental_map()
        live_map: dict[str, dict[str, Any]] = {}
        live_status: dict[str, Any] = {"mode": mode, "used": False}
        if mode.lower() in ("live", "realtime", "intraday"):
            live_map, live_status = _load_or_fetch_live_map(fast_only=True)

        con = self._connect()
        if as_of_date:
            as_of = con.execute(
                "SELECT max(trade_date) FROM daily_bars WHERE trade_date <= ?",
                [as_of_date],
            ).fetchone()[0]
        else:
            as_of = con.execute("SELECT max(trade_date) FROM daily_bars").fetchone()[0]
        as_of_str = str(as_of) if as_of else None
        if not as_of:
            return ScreenResult(None, preset, 0, [], blocked=True,
                                blocker_reason="没有可用交易日数据")

        disclosure_map = {} if fast else _load_disclosure_map(as_of_str)

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
        is_live = _is_live_mode(mode)
        for ts_code, last_close, last_pct, c20, c60, ma20, avg_amt, vol20, n in rows:
            if not (last_close and c20 and c60 and ma20):
                continue
            # Tushare stores `amount` in 千元 (thousands of yuan); convert to yuan.
            avg_amount_yuan = float(avg_amt) * 1000.0 if avg_amt is not None else 0.0
            if avg_amount_yuan < min_amount_cny:
                continue
            ref_price, ref_pct, live = _quote_ref(
                ts_code, float(last_close), last_pct, live_map, is_live=is_live,
            )
            if ref_pct >= 9.8:  # limit-up: can't enter
                continue
            if exclude_st and not _is_main_board(ts_code):
                continue
            sector = sector_map.get(ts_code, "")
            if preferred and not _sector_matches(sector, preferred):
                continue
            if excluded and _sector_matches(sector, excluded):
                continue
            if not price_passes(ref_price, pmin=pmin, eff_max=eff_max):
                continue
            row = {
                "symbol": ts_code,
                "name": resolve_name(ts_code),
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
            if live:
                row.update({
                    "live_price": _to_float(live.get("price")),
                    "live_pct": _to_float(live.get("change_pct")),
                    "live_amount": _to_float(live.get("amount")),
                })
            raw.append(row)

        if is_live and live_map:
            live_status["matched_in_universe"] = sum(1 for r in raw if r.get("live_price") is not None)

        universe = len(raw)
        if universe == 0:
            guide = build_selection_guide(
                preset=preset,
                mode=mode,
                capital_cny=cap,
                price_min_cny=pmin,
                price_max_cny=user_pmax,
                enforce_capital_price_ceiling=enforce_capital_price_ceiling,
                universe_size=0,
                candidate_count=0,
                validation_status=_cached_validation_status().get("verdict", "NOT_RUN"),
                as_of_date=as_of_str,
            )
            return ScreenResult(
                as_of_str, preset, 0, [], blocked=True,
                blocker_reason="无满足流动性/股价区间的标的",
                mode=mode, price_filters=price_filters, selection_guide=guide, capital_cny=cap,
            )

        z = _build_scoring_zmaps(raw)

        from quant.application.scoring_helpers import assign_baseline_scores, finalize_with_ensemble
        from quant.screener.alpha_blend import alpha158_lite_zscore, blend_with_alpha, factor_breakdown

        fb_fn = (lambda _r, _z, _w: []) if fast else factor_breakdown
        assign_baseline_scores(
            raw, z, weights,
            preset=preset, mode=mode, preferred=preferred,
            sector_matches=_sector_matches,
            blend_with_alpha=blend_with_alpha,
            alpha158_lite_zscore=alpha158_lite_zscore,
            factor_breakdown=fb_fn,
        )
        ensemble_meta = finalize_with_ensemble(raw, as_of_date=as_of_str, z=z, mode=mode, fast=fast)

        raw.sort(key=lambda r: r["score"], reverse=True)
        from quant.screener.diversity import apply_diversity_constraints

        top, diversity_notes = apply_diversity_constraints(raw, top_n=max(1, top_n))
        if not top:
            top = raw[: max(1, top_n)]

        from gateway.agents.cn_research.screener_bridge import apply_trading_agents_zh_overlay

        top_dicts = [dict(r) for r in top]
        top_dicts, agent_meta = apply_trading_agents_zh_overlay(
            top_dicts,
            as_of_date=as_of_str,
            mode=mode,
            live_status=live_status,
            regime=_cached_regime_label(),
            capital_cny=cap,
            fast=fast,
        )
        agent_overlay = dict(agent_meta.get("panel") or {})
        agent_overlay["run_id"] = agent_meta.get("run_id")
        overlays = agent_meta.get("overlays") or {}

        # sparkline (last ~30 closes) for the shortlist only
        spark_map: dict[str, list[float]] = {}
        if top_dicts and not fast:
            syms = [r["symbol"] for r in top_dicts]
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

        candidates = [
            Candidate(
                rank=i + 1,
                symbol=r["symbol"],
                name=r.get("name") or resolve_name(r["symbol"]),
                last_close=r["last_close"],
                last_pct=r["last_pct"],
                ret_20=r["ret_20"],
                ret_60=r["ret_60"],
                trend=r["trend"],
                vol_20=r["vol_20"],
                avg_amount=r["avg_amount"],
                score=float(r.get("score") or 0),
                spark=spark_map.get(r["symbol"], []),
                reasons=(overlays.get(r["symbol"], {}).get("bull_points") or _candidate_reasons(r))[:3],
                sector=r.get("sector", ""),
                live_price=r.get("live_price"),
                live_pct=r.get("live_pct"),
                live_amount=r.get("live_amount"),
                pe=r.get("pe"),
                pb=r.get("pb"),
                dividend_yield=r.get("dividend_yield"),
                market_cap=r.get("market_cap"),
                disclosure_flag=r.get("disclosure_flag", ""),
                alpha_score=float(r.get("alpha_score") or 0.0),
                factor_breakdown=list(r.get("factor_breakdown") or []),
            )
            for i, r in enumerate(top_dicts)
        ]
        guide = build_selection_guide(
            preset=preset,
            mode=mode,
            capital_cny=cap,
            price_min_cny=pmin,
            price_max_cny=user_pmax,
            enforce_capital_price_ceiling=enforce_capital_price_ceiling,
            universe_size=universe,
            candidate_count=len(candidates),
            validation_status=_cached_validation_status().get("verdict", "NOT_RUN"),
            as_of_date=as_of_str,
        )
        result = ScreenResult(
            as_of_str, preset, universe, candidates, mode=mode, live_status=live_status,
            diversity_notes=diversity_notes, price_filters=price_filters,
            selection_guide=guide, capital_cny=cap, ensemble_meta=ensemble_meta,
            agent_overlay=agent_overlay,
        )
        if fast:
            _SCREEN_CACHE = (now, cache_key, result)
        return result

    def _score_universe(
        self,
        *,
        preset: str = "balanced",
        as_of_date: str | None = None,
        mode: str = "eod",
        min_amount_cny: float = 0.0,
        exclude_st: bool = False,
        preferred_sectors: list[str] | None = None,
        excluded_sectors: list[str] | None = None,
        price_min_cny: float = 0.0,
        price_max_cny: float | None = None,
        enforce_capital_price_ceiling: bool = False,
        capital_cny: float | None = None,
    ) -> tuple[str | None, list[dict[str, Any]], dict[str, Any], str | None]:
        """Score full investable universe; returns (as_of, scored_rows, live_status, blocker)."""
        import statistics
        import time

        global _UNIVERSE_SCORE_CACHE
        cache_key = f"{preset}|{mode}|{as_of_date or ''}|{min_amount_cny}|{exclude_st}"
        now = time.time()
        if _UNIVERSE_SCORE_CACHE and now - _UNIVERSE_SCORE_CACHE[0] < 120 and _UNIVERSE_SCORE_CACHE[1] == cache_key:
            cached = _UNIVERSE_SCORE_CACHE[2]
            return cached["as_of"], list(cached["raw"]), dict(cached["live_status"]), cached.get("blocker")

        from quant.screener.selection_guide import price_passes, resolve_price_filters

        if capital_cny is None:
            try:
                from gateway.preferences import load_preferences

                capital_cny = load_preferences().capital_cny
            except Exception:
                capital_cny = 5000.0
        pmin, user_pmax, eff_max, _cap = resolve_price_filters(
            price_min_cny=price_min_cny,
            price_max_cny=price_max_cny,
            capital_cny=capital_cny,
            enforce_capital_price_ceiling=enforce_capital_price_ceiling,
        )
        weights = PRESETS.get(preset, PRESETS["balanced"])
        if not self.warehouse.exists():
            return None, [], {"mode": mode}, "数据仓库不存在 — 请先运行「更新数据」"

        preferred = _expand_sector_terms(preferred_sectors or [])
        excluded = _expand_sector_terms(excluded_sectors or [])
        sector_map = _load_sector_map()
        fundamental_map = {} if fast else _load_fundamental_map()
        live_map: dict[str, dict[str, Any]] = {}
        live_status: dict[str, Any] = {"mode": mode, "used": False}
        if mode.lower() in ("live", "realtime", "intraday"):
            live_map, live_status = _load_or_fetch_live_map(fast_only=True)

        con = self._connect()
        if as_of_date:
            as_of = con.execute(
                "SELECT max(trade_date) FROM daily_bars WHERE trade_date <= ?",
                [as_of_date],
            ).fetchone()[0]
        else:
            as_of = con.execute("SELECT max(trade_date) FROM daily_bars").fetchone()[0]
        as_of_str = str(as_of) if as_of else None
        if not as_of:
            return None, [], live_status, "没有可用交易日数据"

        disclosure_map = _load_disclosure_map(as_of_str)

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
        is_live = _is_live_mode(mode)
        for ts_code, last_close, last_pct, c20, c60, ma20, avg_amt, vol20, n in rows:
            if not (last_close and c20 and c60 and ma20):
                continue
            avg_amount_yuan = float(avg_amt) * 1000.0 if avg_amt is not None else 0.0
            if avg_amount_yuan < min_amount_cny:
                continue
            ref_price, ref_pct, live = _quote_ref(
                ts_code, float(last_close), last_pct, live_map, is_live=is_live,
            )
            if ref_pct >= 9.8:
                continue
            if exclude_st and not _is_main_board(ts_code):
                continue
            sector = sector_map.get(ts_code, "")
            if preferred and not _sector_matches(sector, preferred):
                continue
            if excluded and _sector_matches(sector, excluded):
                continue
            if not price_passes(ref_price, pmin=pmin, eff_max=eff_max):
                continue
            row = {
                "symbol": ts_code,
                "name": resolve_name(ts_code),
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
            if live:
                row.update({
                    "live_price": _to_float(live.get("price")),
                    "live_pct": _to_float(live.get("change_pct")),
                    "live_amount": _to_float(live.get("amount")),
                })
            raw.append(row)

        if not raw:
            return as_of_str, [], live_status, "无满足条件的标的"

        z = _build_scoring_zmaps(raw)

        from quant.application.scoring_helpers import assign_baseline_scores, finalize_with_ensemble
        from quant.screener.alpha_blend import alpha158_lite_zscore, blend_with_alpha, factor_breakdown

        assign_baseline_scores(
            raw, z, weights,
            preset=preset, mode=mode, preferred=preferred,
            sector_matches=_sector_matches,
            blend_with_alpha=blend_with_alpha,
            alpha158_lite_zscore=alpha158_lite_zscore,
            factor_breakdown=factor_breakdown,
        )
        finalize_with_ensemble(raw, as_of_date=as_of_str, z=z, mode=mode, fast=True)

        raw.sort(key=lambda r: r["score"], reverse=True)
        _UNIVERSE_SCORE_CACHE = (
            now,
            cache_key,
            {"as_of": as_of_str, "raw": raw, "live_status": live_status, "blocker": None},
        )
        return as_of_str, raw, live_status, None

    def analyze_symbol(
        self,
        symbol: str,
        *,
        preset: str = "balanced",
        as_of_date: str | None = None,
        mode: str = "eod",
        capital_cny: float | None = None,
        preferred_sectors: list[str] | None = None,
        excluded_sectors: list[str] | None = None,
    ) -> dict[str, Any]:
        """Score one symbol against the full universe and return enriched analysis."""
        from quant.scoring.enrichment import enrich_candidate
        from quant.screener.beginner_guide import build_beginner_guide, build_detailed_reasons
        from quant.screener.symbol_search import normalize_symbol_input
        from quant.screener.trade_zones import compute_trade_zones

        norm = normalize_symbol_input(symbol) or symbol.strip().upper()
        if not norm or "." not in norm:
            return {"blocked": True, "blocker_reason": "请输入有效的 A 股代码（如 600519 或 贵州茅台）", "query": symbol}

        as_of_str, scored, live_status, blocker = self._score_universe(
            preset=preset,
            as_of_date=as_of_date,
            mode=mode,
            min_amount_cny=0.0,
            exclude_st=False,
            preferred_sectors=None,
            excluded_sectors=None,
            price_min_cny=0.0,
            price_max_cny=None,
            enforce_capital_price_ceiling=False,
            capital_cny=capital_cny,
        )
        if blocker and not scored:
            return {"blocked": True, "blocker_reason": blocker, "symbol": norm}

        row = next((r for r in scored if r["symbol"] == norm), None)
        if not row:
            return {
                "blocked": True,
                "blocker_reason": f"未找到 {norm} 的足够历史数据，请先「更新数据」",
                "symbol": norm,
                "name": resolve_name(norm),
            }

        rank = scored.index(row) + 1
        universe_size = len(scored)
        percentile = round(100.0 * (1.0 - (rank - 1) / max(universe_size, 1)), 1)

        import duckdb

        con = duckdb.connect(str(self.warehouse), read_only=True)
        srows = con.execute(
            """
            SELECT close FROM (
                SELECT trade_date, close,
                       row_number() OVER (ORDER BY trade_date DESC) AS rn
                FROM daily_bars WHERE ts_code = ?
            ) WHERE rn <= 30 ORDER BY trade_date
            """,
            [norm],
        ).fetchall()
        hist = con.execute(
            """
            SELECT trade_date, open, high, low, close, pct_chg, amount
            FROM daily_bars
            WHERE ts_code = ? AND trade_date <= ?
            ORDER BY trade_date DESC
            LIMIT 80
            """,
            [norm, as_of_str],
        ).fetchall()
        con.close()

        spark = [float(r[0]) for r in srows]
        name = row.get("name") or resolve_name(norm)
        candidate = Candidate(
            rank=rank,
            symbol=norm,
            name=name,
            last_close=row["last_close"],
            last_pct=row["last_pct"],
            ret_20=row["ret_20"],
            ret_60=row["ret_60"],
            trend=row["trend"],
            vol_20=row["vol_20"],
            avg_amount=row["avg_amount"],
            score=row["score"],
            spark=spark,
            reasons=_candidate_reasons(row),
            sector=row.get("sector", ""),
            live_price=row.get("live_price"),
            live_pct=row.get("live_pct"),
            live_amount=row.get("live_amount"),
            pe=row.get("pe"),
            pb=row.get("pb"),
            dividend_yield=row.get("dividend_yield"),
            market_cap=row.get("market_cap"),
            disclosure_flag=row.get("disclosure_flag", ""),
            alpha_score=float(row.get("alpha_score") or 0.0),
            factor_breakdown=list(row.get("factor_breakdown") or []),
        )

        validation_status = _cached_validation_status()
        regime = _cached_regime_label()
        cap = float(capital_cny or 5000.0)
        cand_dict = candidate.to_dict()
        enriched = enrich_candidate(
            cand_dict,
            rank=rank,
            preset=preset,
            as_of_date=as_of_str or "",
            capital_cny=cap,
            validation_status=validation_status,
            regime=regime,
        )
        trade_zones = compute_trade_zones(
            symbol=norm,
            price=float(row.get("live_price") or candidate.last_close),
            trend_pct=float(candidate.trend) * 100,
            vol_20=float(candidate.vol_20),
            last_pct=float(row.get("live_pct") if row.get("live_pct") is not None else candidate.last_pct),
        )
        detailed_reasons = build_detailed_reasons(enriched, enriched.get("factor_breakdown") or candidate.factor_breakdown)
        qty = int(enriched.get("suggested_qty") or 0)
        beginner_guide = build_beginner_guide(
            symbol=norm,
            name=name,
            price=float(row.get("live_price") or candidate.last_close),
            qty=qty or 100,
            notional=float(candidate.last_close) * (qty or 100),
            zones=trade_zones,
            reasons=detailed_reasons or candidate.reasons,
            data_as_of=as_of_str or "",
            data_tier=mode.upper(),
            broker_handoff="券商 App 登录后预填订单，由你亲自确认",
        )
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
            "blocked": False,
            "symbol": norm,
            "name": name,
            "as_of_date": as_of_str,
            "preset": preset,
            "mode": mode,
            "rank": rank,
            "universe_size": universe_size,
            "percentile_top": percentile,
            "score": round(float(row["score"]), 3),
            "alpha_score": round(float(row.get("alpha_score") or 0.0), 4),
            "candidate": cand_dict,
            "enriched": enriched,
            "trade_zones": trade_zones,
            "detailed_reasons": detailed_reasons,
            "beginner_guide": beginner_guide,
            "plain_language": _plain_language(candidate),
            "institutional_report": _institutional_report(candidate, history),
            "live_status": live_status,
            "risk_notes": [
                "仅研究/模拟交易，不构成投资建议",
                "A股 T+1：买入当日不可卖出",
                "涨停附近不追入，跌破止损/趋势无效必须退出模拟计划",
            ],
            "history": history,
        }

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
        analysis = self.analyze_symbol(
            symbol,
            preset=preset,
            as_of_date=as_of_date,
            mode=mode,
            preferred_sectors=preferred_sectors,
            excluded_sectors=excluded_sectors,
        )
        if analysis.get("blocked"):
            return {
                "symbol": analysis.get("symbol") or symbol,
                "name": analysis.get("name") or resolve_name(symbol),
                "as_of_date": None,
                "rank": None,
                "candidate": None,
                "enriched": None,
                "trade_zones": {},
                "detailed_reasons": [],
                "beginner_guide": {},
                "plain_language": analysis.get("blocker_reason", "无法生成个股解释"),
                "institutional_report": None,
                "risk_notes": [
                    "仅研究/模拟交易，不构成投资建议",
                    "A股 T+1：买入当日不可卖出",
                ],
                "history": [],
            }
        out = dict(analysis)
        out.pop("blocked", None)
        return out

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


def _build_scoring_zmaps(raw: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """Size+industry neutral z for core factors; industry-neutral for fundamentals."""
    from quant.features.neutralization import build_zscore_layers, industry_neutral_zscores, cross_section_zscores

    layers = build_zscore_layers(raw)
    z = dict(layers["size_industry"])
    industries = {r["symbol"]: r.get("sector") or "未知" for r in raw}
    if any(r.get("live_pct") is not None for r in raw):
        z["live_pct"] = zscores_nullable(raw, "live_pct")
        z["live_amount"] = zscores_nullable(raw, "live_amount")
    for optional in ("pe", "pb", "dividend_yield", "market_cap"):
        if any(r.get(optional) is not None for r in raw):
            vals = {r["symbol"]: float(r[optional]) for r in raw if r.get(optional) is not None}
            z[optional] = industry_neutral_zscores(vals, industries)
    return z


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

    return _load_sector_map_cached()


@lru_cache(maxsize=1)
def _load_sector_map_cached() -> dict[str, str]:
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
    return _load_fundamental_map_cached()


@lru_cache(maxsize=1)
def _load_fundamental_map_cached() -> dict[str, dict[str, Any]]:
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


def _load_disclosure_map(as_of_date: str | None = None) -> dict[str, dict[str, Any]]:
    import json

    from quant.disclosures.pit_filter import filter_point_in_time

    path = ROOT / "data" / "disclosures" / "disclosures_cninfo_official.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = list(data.get("rows", []))
    cutoff = as_of_date
    if not cutoff:
        from datetime import datetime

        cutoff = datetime.now().strftime("%Y-%m-%d")
    pit = filter_point_in_time(rows, analysis_cutoff=cutoff)
    out: dict[str, dict[str, Any]] = {}
    for row in pit.passed:
        code = str(row.get("stock_code", "")).zfill(6)
        exchange = str(row.get("exchange", "")).upper()
        suffix = "SH" if exchange.startswith("SSE") or code.startswith("6") else "SZ"
        out[f"{code}.{suffix}"] = row
    return out


def _is_live_mode(mode: str) -> bool:
    return str(mode or "").lower() in ("live", "realtime", "intraday")


def _quote_ref(
    ts_code: str,
    last_close: float,
    last_pct: float | None,
    live_map: dict[str, dict[str, Any]],
    *,
    is_live: bool,
) -> tuple[float, float, dict[str, Any] | None]:
    live = live_map.get(ts_code)
    live_price = _to_float(live.get("price")) if live else None
    live_pct = _to_float(live.get("change_pct")) if live and live.get("change_pct") is not None else None
    if is_live and live_price:
        return live_price, float(live_pct if live_pct is not None else (last_pct or 0.0)), live
    return float(last_close), float(last_pct or 0.0), live


def _live_symbol(row: dict[str, Any]) -> str:
    from quant.application.live_market_service import normalize_ts_code

    return normalize_ts_code(str(row.get("code", "")))


def _load_or_fetch_live_map(*, fast_only: bool = False) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Load cached live quotes; optional network fetch when cache empty."""
    import time

    global _LIVE_CACHE
    now = time.time()
    if _LIVE_CACHE and now - _LIVE_CACHE[0] < 60:
        live_map = _LIVE_CACHE[1]
        status = dict(_LIVE_CACHE[2])
        status["source"] = f"{status.get('source', 'fabric')}:cache"
        return live_map, status

    from quant.application.live_market_service import ensure_live_quotes, snapshot_rows

    status: dict[str, Any] = {"mode": "live", "used": False, "source": "none"}
    snap: dict[str, Any] = {}
    snap = ensure_live_quotes(refresh=False, max_age_sec=900)
    rows = snapshot_rows(snap)
    if rows:
        status.update({
            "source": "persisted" if not snap.get("stale_fallback") else "persisted_stale",
            "retrieved_at": snap.get("retrieved_at"),
            "provider": snap.get("provider"),
            "row_count": len(rows),
            "success": snap.get("success"),
            "freshness": snap.get("freshness"),
            "stale_fallback": bool(snap.get("stale_fallback")),
        })
    elif not fast_only:
        try:
            snap = ensure_live_quotes(refresh=True, max_age_sec=120)
            rows = snapshot_rows(snap)
            status.update({k: v for k, v in snap.items() if k != "rows"})
            status["source"] = "refresh"
            status["row_count"] = len(rows)
        except Exception as exc:
            status.update({"blocked": True, "error": str(exc)[:160]})

    if not rows and not fast_only:
        try:
            from quant.application.live_market_service import fetch_live_snapshot

            snap = fetch_live_snapshot(require_live=False)
            rows = snapshot_rows(snap)
            status.update({k: v for k, v in snap.items() if k != "rows"})
            status["source"] = "fabric_fetch"
            status["row_count"] = len(rows)
        except Exception as exc:
            status.update({"blocked": True, "error": str(exc)[:160]})

    if not rows:
        status.update({
            "used": False,
            "fallback": "eod_factors_only",
            "hint": snap.get("reason") or "实时行情未就绪：请用「收盘数据」模式（约 1 秒），或在「高级·数据」先刷新实时行情。",
        })

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
    display = f"{candidate.name}（{candidate.symbol}）" if candidate.name else candidate.symbol
    parts = [
        f"{display} 当前排名第 {candidate.rank}，综合分 {candidate.score:.2f}。",
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
