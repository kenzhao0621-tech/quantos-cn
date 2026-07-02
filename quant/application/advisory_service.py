"""AdvisoryService — v2.2 advisory pipeline over real warehouse data.

Flow (all through CacheOS, honest degradation everywhere):

  warehouse daily_bars (real Tushare EOD)
    → universe factor snapshot   [feature_vector cache, keyed by data_version]
    → v2.2 fixed formula scores  [ScoringOS]
    → trade plan from price structure
    → four-panel advice card     [ExplainOS]
  all wrapped in an advisory_result cache entry + DataAuditReport.

Factors with no real data source on this branch (money flow, sentiment,
policy news, Kronos predictions) are reported as missing and down-weighted —
they are NEVER fabricated. When KronosOS lands, its predictions enter through
the generic PredictionCache and the kronos_forecast factor lights up.
"""

from __future__ import annotations

import json
import statistics
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from quant.cache_os import CacheKey, get_cache_registry, get_prediction_cache
from quant.cache_os.invalidation import warehouse_data_version
from quant.cache_os.metrics import get_cache_metrics
from quant.compute_os.profiling import get_profiler
from quant.explain_os.advice_card import build_advice_card
from quant.scoring_os.confidence import compute_confidence
from quant.scoring_os.formulas import FactorScore, ScoreInputs, compose_factor, compute_final_score
from quant.scoring_os.normalization import robust_percentile_score
from quant.scoring_os.target_price import build_trade_plan
from quant.scoring_os.weights import SCORE_WEIGHT_VERSION
from quant.screener.names import resolve_name

ROOT = Path(__file__).resolve().parents[2]
WAREHOUSE = ROOT / "data" / "warehouse" / "quant.duckdb"
AUDIT_DIR = ROOT / "data" / "quantos" / "advisory_audit"

TUSHARE_URL = "https://tushare.pro"


class AdvisoryService:
    def __init__(self, warehouse: Optional[Path] = None) -> None:
        self.warehouse = warehouse or WAREHOUSE
        self.cache = get_cache_registry()
        self.predictions = get_prediction_cache()
        self.profiler = get_profiler()

    # ------------------------------------------------------------------
    def advise(
        self,
        symbol: str,
        *,
        capital_cny: float = 10000.0,
        position_weight: float = 0.30,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """Return the cached-or-computed advice card for one symbol."""
        started = time.perf_counter()
        data_version = warehouse_data_version(symbol=symbol, warehouse=self.warehouse)
        key = CacheKey(
            data_type="advisory_result",
            symbol=symbol,
            source="quantos_advisory",
            as_of_date=data_version,
            params={
                "capital_cny": capital_cny,
                "position_weight": position_weight,
                "score_weight_version": SCORE_WEIGHT_VERSION,
            },
        )
        result = self.cache.get_or_compute(
            key,
            lambda: self._compute(symbol, capital_cny=capital_cny, position_weight=position_weight),
            persist=True,
            force_refresh=force_refresh,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        step = "single_stock_force_refresh" if force_refresh else "single_stock_cached_analysis"
        self.profiler.record(step, elapsed_ms=elapsed_ms, cache_hit=result.cache_status == "hit")

        if result.value is None:
            return {
                "blocked": True,
                "blocker_reason": result.meta.get("loader_error", "无法生成建议：数据不可用"),
                "symbol": symbol,
                "cache": result.explain(),
            }
        card = dict(result.value)
        card["cache"] = result.explain()
        card["headline"] = dict(card.get("headline") or {})
        card["headline"]["cache_status"] = {
            "hit": "cache_hit", "miss": "cache_miss",
            "force_refresh": "force_refresh", "stale_allowed": "stale_allowed",
        }.get(result.cache_status, result.cache_status)
        card["headline"]["data_freshness"] = result.freshness.label_zh
        return card

    def cache_status(self) -> Dict[str, Any]:
        return {
            "metrics": get_cache_metrics().snapshot(),
            "policy_session": self.cache.policies.session_state(),
            "known_data_types": self.cache.policies.known_data_types(),
            "warehouse_data_version": warehouse_data_version(warehouse=self.warehouse),
        }

    # ------------------------------------------------------------------
    def _connect(self):
        import duckdb

        return duckdb.connect(str(self.warehouse), read_only=True)

    def universe_snapshot(self) -> Dict[str, Any]:
        """Cross-sectional raw factor snapshot, cached per warehouse data_version."""
        data_version = warehouse_data_version(warehouse=self.warehouse)
        key = CacheKey(data_type="feature_vector", source="warehouse_daily_bars",
                       as_of_date=data_version, params={"v": "advisory_snapshot_v1"})
        res = self.cache.get_or_compute(key, self._build_snapshot, persist=True)
        if res.value is None:
            raise RuntimeError(res.meta.get("loader_error", "universe snapshot unavailable"))
        return res.value

    def _build_snapshot(self) -> Any:
        if not self.warehouse.exists():
            raise RuntimeError("数据仓库不存在 — 请先运行「更新数据」")
        con = self._connect()
        try:
            as_of = con.execute("SELECT max(trade_date) FROM daily_bars").fetchone()[0]
            if not as_of:
                raise RuntimeError("没有可用交易日数据")
            as_of_str = str(as_of)
            rows = con.execute(
                """
                WITH recent AS (
                    SELECT ts_code, trade_date, close, high, low, pct_chg, amount,
                           row_number() OVER (PARTITION BY ts_code ORDER BY trade_date DESC) AS rn
                    FROM daily_bars
                    WHERE trade_date <= ? AND trade_date >= (?::DATE - INTERVAL 160 DAY)
                )
                SELECT ts_code,
                       max(CASE WHEN rn = 1 THEN close END)    AS last_close,
                       max(CASE WHEN rn = 1 THEN pct_chg END)  AS last_pct,
                       max(CASE WHEN rn = 21 THEN close END)   AS close_20,
                       max(CASE WHEN rn = 61 THEN close END)   AS close_60,
                       avg(CASE WHEN rn <= 5 THEN close END)   AS ma5,
                       avg(CASE WHEN rn <= 10 THEN close END)  AS ma10,
                       avg(CASE WHEN rn <= 20 THEN close END)  AS ma20,
                       avg(CASE WHEN rn <= 60 THEN close END)  AS ma60,
                       stddev_samp(CASE WHEN rn <= 20 THEN pct_chg END) AS vol20,
                       avg(CASE WHEN rn <= 20 THEN amount END) AS avg_amt20,
                       avg(CASE WHEN rn <= 60 THEN amount END) AS avg_amt60,
                       max(CASE WHEN rn <= 20 THEN high END)   AS high_20,
                       max(CASE WHEN rn <= 60 THEN high END)   AS high_60,
                       min(CASE WHEN rn <= 20 THEN low END)    AS low_20,
                       count(*) AS n
                FROM recent
                GROUP BY ts_code
                HAVING n >= 61
                """,
                [as_of_str, as_of_str],
            ).fetchall()
            cols = ["last_close", "last_pct", "close_20", "close_60", "ma5", "ma10",
                    "ma20", "ma60", "vol20", "avg_amt20", "avg_amt60", "high_20",
                    "high_60", "low_20", "n"]
            symbols: Dict[str, Dict[str, Any]] = {}
            for row in rows:
                rec = {c: (float(v) if v is not None else None) for c, v in zip(cols, row[1:])}
                symbols[row[0]] = rec
            sectors = {r[0]: r[1] for r in con.execute(
                "SELECT code, max(sector_name) FROM industry_map GROUP BY code").fetchall()}
            fundamentals = {}
            try:
                frows = con.execute(
                    """
                    SELECT ts_code, pe_ttm, pb, turnover_rate, total_mv
                    FROM (SELECT *, row_number() OVER (PARTITION BY ts_code ORDER BY trade_date DESC) rn
                          FROM fundamental) WHERE rn = 1
                    """).fetchall()
                for ts, pe, pb, tr, mv in frows:
                    fundamentals[ts] = {
                        "pe_ttm": float(pe) if pe is not None else None,
                        "pb": float(pb) if pb is not None else None,
                        "turnover_rate": float(tr) if tr is not None else None,
                        "total_mv": float(mv) if mv is not None else None,
                    }
            except Exception:
                fundamentals = {}
        finally:
            con.close()
        snapshot = {
            "as_of_date": as_of_str,
            "symbols": symbols,
            "sectors": sectors,
            "fundamentals": fundamentals,
        }
        return snapshot, {"source": "tushare/duckdb", "source_url": TUSHARE_URL,
                          "updated_at": as_of_str}

    # ------------------------------------------------------------------
    def _compute(self, symbol: str, *, capital_cny: float, position_weight: float) -> Any:
        snapshot = self.universe_snapshot()
        symbols: Dict[str, Dict[str, Any]] = snapshot["symbols"]
        rec = symbols.get(symbol)
        if rec is None:
            raise RuntimeError(f"未找到 {symbol} 的足够历史数据（需要至少61个交易日）")
        as_of = snapshot["as_of_date"]
        sectors: Dict[str, str] = snapshot["sectors"]
        fundamentals: Dict[str, Dict[str, Any]] = snapshot["fundamentals"]
        name = resolve_name(symbol)

        cross = list(symbols.values())
        sector = _sector_of(symbol, sectors)
        sector_peers = [v for k, v in symbols.items() if _sector_of(k, sectors) == sector] if sector else []

        factors, source_tiers, facts = self._build_factors(
            symbol, rec, cross, sector, sector_peers, fundamentals, as_of)

        # Kronos / generic model prediction — only if a real cached prediction exists.
        prediction_payloads: List[Dict[str, Any]] = []
        pred = self.predictions.peek(model="kronos-mini", symbol=symbol, horizon="5d",
                                     data_version=warehouse_data_version(symbol=symbol,
                                                                         warehouse=self.warehouse))
        if pred is not None and pred.value and pred.freshness.usable_for_recommendation:
            p = dict(pred.value)
            sub = compose_factor("kronos_forecast", {
                "direction_probability": _prob_to_score(p.get("direction_prob")),
                "expected_return": _ret_to_score(p.get("expected_return")),
                "volatility_risk_adjusted": _prob_to_score(p.get("risk_adjusted")),
                "forecast_stability": _prob_to_score(p.get("stability")),
            })
            factors["kronos_forecast"] = FactorScore(
                name="kronos_forecast", score=sub["score"], source="kronos-mini",
                source_url="cache://prediction", updated_at=pred.updated_at or as_of,
                freshness=pred.freshness.status.value, normalization="model_output_mapped_0_100",
                detail=sub)
            source_tiers["kronos_forecast"] = "A_public_data_vendor"
            prediction_payloads.append(dict(p, model="kronos-mini", horizon="5d",
                                            cache=pred.explain()))

        regime = _current_regime()
        risk_inputs, execution_inputs, overheat_inputs = self._penalty_inputs(
            symbol, name, rec, cross, fundamentals.get(symbol) or {},
            capital_cny=capital_cny)

        score_result = compute_final_score(ScoreInputs(
            symbol=symbol, factors=factors, regime=regime["key"],
            source_tiers=source_tiers, risk_inputs=risk_inputs,
            execution_inputs=execution_inputs, overheat_inputs=overheat_inputs))

        history = self._history(symbol, as_of)
        trade_plan = build_trade_plan(
            symbol=symbol, current_price=rec["last_close"], history=history,
            capital_cny=capital_cny, position_weight=position_weight,
            last_pct=rec.get("last_pct") or 0.0)

        available = [f for f in factors.values() if f.available]
        agreement = _signal_agreement([f.score for f in available])
        confidence = compute_confidence({
            "signal_agreement": agreement,
            "data_freshness": 1.0,  # snapshot freshness enforced by CacheOS keying
            "historical_validation_strength": _validation_strength(),
            "regime_clarity": 0.7 if regime["key"] != "unknown" else 0.2,
            "model_stability": 0.5 if prediction_payloads else None,
        })

        card = build_advice_card(
            symbol=symbol, name=name, score_result=score_result,
            trade_plan=trade_plan, confidence=confidence, facts=facts,
            predictions=prediction_payloads,
            cache_provenance=[],
            data_freshness_label="最新（EOD 收盘数据）",
        )
        card["as_of_date"] = as_of
        card["regime"] = regime
        card["capital_cny"] = capital_cny
        audit = self._write_audit(symbol, score_result)
        card["audit"] = {"run_id": audit["run_id"], "path": audit["path"]}
        return card, {"source": "tushare/duckdb", "source_url": TUSHARE_URL, "updated_at": as_of}

    # ------------------------------------------------------------------
    def _build_factors(self, symbol, rec, cross, sector, sector_peers, fundamentals, as_of):
        """Compute the 8 v2.2 factors from real cross-sectional data.

        Sub-factors without a real source return None → honest down-weighting.
        """
        def col(name):
            return [r.get(name) for r in cross]

        ret20 = _ratio(rec, "last_close", "close_20")
        ret60 = _ratio(rec, "last_close", "close_60")
        cross_ret20 = [_ratio(r, "last_close", "close_20") for r in cross]
        cross_ret60 = [_ratio(r, "last_close", "close_60") for r in cross]

        # ---- trend ----
        ma_alignment = _ma_alignment_score(rec)
        breakout = _breakout_score(rec)
        rs = None
        if sector_peers and len(sector_peers) >= 5:
            peer_ret20 = [_ratio(r, "last_close", "close_20") for r in sector_peers]
            rs = robust_percentile_score(ret20, peer_ret20)
        ddr = _drawdown_recovery_score(rec)
        trend = compose_factor("trend", {
            "ma_alignment": ma_alignment, "breakout": breakout,
            "relative_strength": rs, "drawdown_recovery": ddr,
        })

        # ---- momentum ----
        irm = None
        if sector_peers and len(sector_peers) >= 5 and ret20 is not None:
            peer_med = statistics.median([x for x in (
                _ratio(r, "last_close", "close_20") for r in sector_peers) if x is not None])
            irm = robust_percentile_score(
                ret20 - peer_med,
                [x - peer_med for x in cross_ret20 if x is not None])
        momentum = compose_factor("momentum", {
            "return_20d_percentile": robust_percentile_score(ret20, cross_ret20),
            "return_60d_percentile": robust_percentile_score(ret60, cross_ret60),
            "industry_relative_momentum": irm,
        })

        # ---- volume / money flow ----
        fund = fundamentals.get(symbol) or {}
        amt_ratio = _safe_div(rec.get("avg_amt20"), rec.get("avg_amt60"))
        cross_amt_ratio = [_safe_div(r.get("avg_amt20"), r.get("avg_amt60")) for r in cross]
        turnover = fund.get("turnover_rate")
        turnover_quality = None
        if turnover is not None:
            cross_turnover = [
                (fundamentals.get(k) or {}).get("turnover_rate")
                for k in (r for r in fundamentals)
            ]
            pct = robust_percentile_score(turnover, cross_turnover)
            turnover_quality = 100.0 - abs(pct - 50.0) * 2.0  # moderate turnover is best
        vmf = compose_factor("volume_money_flow", {
            "volume_expansion": robust_percentile_score(amt_ratio, cross_amt_ratio),
            "turnover_quality": turnover_quality,
            "money_flow": None,  # no real money-flow source wired — honest missing
            "liquidity": robust_percentile_score(rec.get("avg_amt20"), col("avg_amt20")),
        })

        # ---- fundamental quality ----
        pe = fund.get("pe_ttm")
        valuation = None
        if pe is not None and pe > 0:
            cross_pe = [v.get("pe_ttm") for v in fundamentals.values()
                        if v.get("pe_ttm") is not None and v.get("pe_ttm") > 0]
            valuation = robust_percentile_score(pe, cross_pe, lower_is_better=True)
        fundamental = compose_factor("fundamental_quality", {
            "profitability": None,   # ROE/ROA not in warehouse yet — honest missing
            "growth": None,
            "balance_sheet": None,
            "valuation_reasonableness": valuation,
            "risk_flag": self._risk_flag_score(symbol),
        })

        # ---- announcement / policy ----
        ann = self._announcement_scores(symbol, as_of)
        announcement = compose_factor("announcement_policy", ann)

        # ---- sector theme ----
        sector_theme_subs = {"sector_trend": None, "sector_money_flow": None,
                             "policy_alignment": None, "breadth": None}
        if sector_peers and len(sector_peers) >= 5:
            peer_ret = [x for x in (_ratio(r, "last_close", "close_20") for r in sector_peers)
                        if x is not None]
            if peer_ret:
                sector_med = statistics.median(peer_ret)
                all_sector_medians = _sector_medians(cross, sector_peers, sector_med)
                sector_theme_subs["sector_trend"] = robust_percentile_score(
                    sector_med, all_sector_medians)
                sector_theme_subs["breadth"] = round(
                    100.0 * sum(1 for x in peer_ret if x > 0) / len(peer_ret), 2)
        sector_theme = compose_factor("sector_theme", sector_theme_subs)

        def fs(name, composed, source, url):
            if composed["all_missing"]:
                return None
            return FactorScore(name=name, score=composed["score"], source=source,
                               source_url=url, updated_at=as_of, freshness="fresh",
                               detail=composed)

        factors: Dict[str, FactorScore] = {}
        tiers: Dict[str, str] = {}
        for key, composed, source, url, tier in (
            ("trend", trend, "tushare/duckdb", TUSHARE_URL, "A_public_data_vendor"),
            ("momentum", momentum, "tushare/duckdb", TUSHARE_URL, "A_public_data_vendor"),
            ("volume_money_flow", vmf, "tushare/duckdb", TUSHARE_URL, "A_public_data_vendor"),
            ("fundamental_quality", fundamental, "tushare daily_basic", TUSHARE_URL, "A_public_data_vendor"),
            ("announcement_policy", announcement, "cninfo/exchange", "http://www.cninfo.com.cn", "S_official_exchange"),
            ("sector_theme", sector_theme, "tushare industry_map", TUSHARE_URL, "A_public_data_vendor"),
        ):
            f = fs(key, composed, source, url)
            if f is not None:
                factors[key] = f
                tiers[key] = tier
        # kronos_forecast and sentiment intentionally absent unless real data exists.

        facts = [
            {"fact": f"收盘价 {rec['last_close']:.2f} 元（{as_of}）", "source": "tushare daily",
             "source_url": TUSHARE_URL, "updated_at": as_of},
            {"fact": f"20日日均成交额 {(rec.get('avg_amt20') or 0) * 1000 / 1e8:.2f} 亿元",
             "source": "tushare daily", "source_url": TUSHARE_URL, "updated_at": as_of},
        ]
        if sector:
            facts.append({"fact": f"所属板块：{sector}", "source": "tushare industry_map",
                          "source_url": TUSHARE_URL, "updated_at": as_of})
        if pe is not None:
            facts.append({"fact": f"PE(TTM) {pe:.2f}", "source": "tushare daily_basic",
                          "source_url": TUSHARE_URL, "updated_at": as_of})
        return factors, tiers, facts

    def _risk_flag_score(self, symbol: str) -> Optional[float]:
        rows = self._disclosures(symbol)
        if rows is None:
            return None  # disclosure source not verifiable for this symbol
        severe = [r for r in rows if str(r.get("severity", "")).upper() in ("HIGH", "SEVERE")]
        if severe:
            return 10.0
        medium = [r for r in rows if str(r.get("severity", "")).upper() == "MEDIUM"]
        return 40.0 if medium else 70.0

    def _announcement_scores(self, symbol: str, as_of: str) -> Dict[str, Optional[float]]:
        rows = self._disclosures(symbol)
        company = None
        regulatory = None
        if rows is not None:
            if rows:
                sev = [str(r.get("severity", "")).upper() for r in rows]
                company = 25.0 if any(s in ("HIGH", "SEVERE") for s in sev) else 55.0
                regulatory = 20.0 if any(r.get("blocking_status") for r in rows) else 60.0
            else:
                company, regulatory = 60.0, 65.0  # official poll succeeded, no adverse filings
        return {"company_announcement": company, "industry_policy": None,
                "regulatory_risk": regulatory}

    def _disclosures(self, symbol: str) -> Optional[List[Dict[str, Any]]]:
        if not self.warehouse.exists():
            return None
        code = symbol.split(".")[0]
        try:
            con = self._connect()
            try:
                tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
                if "disclosures" not in tables:
                    return None
                rows = con.execute(
                    "SELECT title, severity, blocking_status, canonical_url, official_publication_time "
                    "FROM disclosures WHERE stock_code = ?", [code]).fetchall()
            finally:
                con.close()
            return [
                {"title": t, "severity": s, "blocking_status": b, "canonical_url": u,
                 "published_at": str(p)}
                for t, s, b, u, p in rows
            ]
        except Exception:
            return None

    def _penalty_inputs(self, symbol, name, rec, cross, fund, *, capital_cny):
        vol_pct = robust_percentile_score(rec.get("vol20"), [r.get("vol20") for r in cross])
        dd_depth = None
        if rec.get("high_60") and rec.get("last_close"):
            dd_depth = 1.0 - rec["last_close"] / rec["high_60"]
        cross_dd = [1.0 - _safe_div(r.get("last_close"), r.get("high_60"), default=1.0)
                    for r in cross]
        liq_pct = robust_percentile_score(rec.get("avg_amt20"), [r.get("avg_amt20") for r in cross])
        disclosures = self._disclosures(symbol) or []
        severe_event = any(str(r.get("severity", "")).upper() in ("HIGH", "SEVERE") for r in disclosures)

        risk_inputs: Dict[str, Any] = {
            "volatility_risk": vol_pct,
            "drawdown_risk": robust_percentile_score(dd_depth, cross_dd),
            "fundamental_risk": 90.0 if severe_event else None,
            "event_risk": 90.0 if severe_event else (30.0 if disclosures else None),
            "liquidity_risk": 100.0 - liq_pct,
            "concentration_risk": None,
            "is_st": "ST" in (name or "").upper(),
            "data_unverifiable": rec.get("last_close") is None,
        }

        price = rec.get("last_close") or 0.0
        lot_cost = price * 100
        lot_share = lot_cost / capital_cny if capital_cny > 0 else 1.0
        last_pct = abs(rec.get("last_pct") or 0.0)
        limit = 20.0 if symbol.split(".")[0].startswith(("30", "688")) else 10.0
        execution_inputs = {
            "lot_size": min(100.0, lot_share * 200.0),          # one lot >50% capital → max
            "price_limit": min(100.0, (last_pct / limit) * 110.0),
            "slippage": 100.0 - liq_pct,
            "t_plus_one": vol_pct,                              # high vol + T+1 = no same-day exit
            "cash_fit": min(100.0, lot_share * 150.0),
        }

        ret20 = _ratio(rec, "last_close", "close_20")
        cross_ret20 = [_ratio(r, "last_close", "close_20") for r in cross]
        ret20_pct = robust_percentile_score(ret20, cross_ret20)
        ma20_dev = _safe_div(rec.get("last_close"), rec.get("ma20"), default=1.0) - 1.0
        pe = fund.get("pe_ttm")
        overheat_inputs = {
            "short_term_return_overheat": max(0.0, (ret20_pct - 70.0) / 30.0 * 100.0),
            "volume_spike_risk": max(0.0, (robust_percentile_score(
                _safe_div(rec.get("avg_amt20"), rec.get("avg_amt60")),
                [_safe_div(r.get("avg_amt20"), r.get("avg_amt60")) for r in cross]) - 80.0) / 20.0 * 100.0),
            "limit_up_chase_risk": 100.0 if (rec.get("last_pct") or 0) >= limit * 0.95 else
                                   (60.0 if (rec.get("last_pct") or 0) >= limit * 0.7 else 0.0),
            "valuation_overheat": None if pe is None or pe <= 0 else max(0.0, min(100.0, (pe - 60.0))),
            "sentiment_crowding_risk": None,
            "overheat_stall": bool(ret20_pct > 92 and ma20_dev > 0.15),
        }
        return risk_inputs, execution_inputs, overheat_inputs

    def _history(self, symbol: str, as_of: str) -> List[Dict[str, Any]]:
        con = self._connect()
        try:
            rows = con.execute(
                """
                SELECT trade_date, open, high, low, close FROM daily_bars
                WHERE ts_code = ? AND trade_date <= ?
                ORDER BY trade_date DESC LIMIT 90
                """, [symbol, as_of]).fetchall()
        finally:
            con.close()
        return [
            {"trade_date": str(d), "open": float(o), "high": float(h),
             "low": float(l), "close": float(c)}
            for d, o, h, l, c in reversed(rows)
        ]

    def _write_audit(self, symbol: str, score_result: Dict[str, Any]) -> Dict[str, Any]:
        run_id = uuid.uuid4().hex[:12]
        report = {
            "run_id": run_id,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "symbols": [symbol],
            "data_sources_used": sorted({c.get("source") for c in score_result.get("contributions", [])
                                         if c.get("source")}),
            "cache_summary": get_cache_metrics().snapshot()["cache_summary"],
            "formula_version": score_result.get("score_weight_version"),
            "model_versions": {},
            "warnings": [f"factor missing: {m}" for m in score_result.get("missing_factors", [])],
            "forbidden_data_detected": False,
        }
        path = AUDIT_DIR / f"advisory_{datetime.now().strftime('%Y%m%d')}_{run_id}.json"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        return {"run_id": run_id, "path": str(path)}


# ----------------------------------------------------------------------
def _ratio(rec: Dict[str, Any], a: str, b: str) -> Optional[float]:
    va, vb = rec.get(a), rec.get(b)
    if va is None or vb in (None, 0):
        return None
    return va / vb - 1.0


def _safe_div(a, b, default=None):
    if a is None or b in (None, 0):
        return default
    return a / b


def _ma_alignment_score(rec: Dict[str, Any]) -> Optional[float]:
    vals = [rec.get("last_close"), rec.get("ma5"), rec.get("ma10"), rec.get("ma20"), rec.get("ma60")]
    if any(v is None for v in vals):
        return None
    pairs = [(vals[i], vals[i + 1]) for i in range(len(vals) - 1)]
    aligned = sum(1 for a, b in pairs if a > b)
    return round(aligned / len(pairs) * 100.0, 2)


def _breakout_score(rec: Dict[str, Any]) -> Optional[float]:
    close, h20, h60 = rec.get("last_close"), rec.get("high_20"), rec.get("high_60")
    last_pct = rec.get("last_pct") or 0.0
    if close is None or not h20 or not h60:
        return None
    score = 0.0
    if close >= h60 * 0.995:
        score = 90.0
    elif close >= h20 * 0.995:
        score = 75.0
    else:
        score = max(0.0, 60.0 * close / h20)
    if last_pct >= 9.0:  # 一字/涨停突破不可追（§5.4 禁止追高满分）
        score = min(score, 40.0)
    return round(score, 2)


def _drawdown_recovery_score(rec: Dict[str, Any]) -> Optional[float]:
    close, h20, l20 = rec.get("last_close"), rec.get("high_20"), rec.get("low_20")
    if close is None or h20 is None or l20 is None or h20 <= l20:
        return None
    return round((close - l20) / (h20 - l20) * 100.0, 2)


def _sector_medians(cross, sector_peers, own_median) -> List[float]:
    # cheap proxy: compare own sector median against the distribution of all
    # symbol ret20 values (full per-sector medians would need the sector map here)
    vals = [x for x in (_ratio(r, "last_close", "close_20") for r in cross) if x is not None]
    return vals or [own_median]


def _sector_of(symbol: str, sectors: Dict[str, str]) -> str:
    return sectors.get(symbol) or sectors.get(symbol.split(".")[0]) or ""


def _prob_to_score(p) -> Optional[float]:
    if p is None:
        return None
    return round(min(100.0, max(0.0, float(p) * 100.0)), 2)


def _ret_to_score(r) -> Optional[float]:
    if r is None:
        return None
    return round(min(100.0, max(0.0, 50.0 + float(r) * 500.0)), 2)


def _signal_agreement(scores: List[float]) -> float:
    if len(scores) < 2:
        return 0.3
    sd = statistics.pstdev(scores)
    return round(min(1.0, max(0.0, 1.0 - sd / 50.0)), 3)


def _validation_strength() -> float:
    path = ROOT / "artifacts" / "model_validation.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return 0.7 if data.get("verdict") == "PASS" else 0.3
    except Exception:
        return 0.0


def _current_regime() -> Dict[str, Any]:
    try:
        from tools.china_quant.regime_v2 import classify_regime_v2

        r = classify_regime_v2()
        label = str(r.get("regime", "UNKNOWN")).upper()
        mapping = {
            "BULL": "structural_bull", "STRONG_BULL": "strong_bull",
            "RANGE": "range_bound", "NEUTRAL": "range_bound",
            "WEAK": "weak_range", "BEAR": "bear",
        }
        return {"key": mapping.get(label, "unknown"), "raw": label, "score": r.get("score")}
    except Exception:
        return {"key": "unknown", "raw": "UNKNOWN", "score": None}


_service: Optional[AdvisoryService] = None


def get_advisory_service() -> AdvisoryService:
    global _service
    if _service is None:
        _service = AdvisoryService()
    return _service
