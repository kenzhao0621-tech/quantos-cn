"""LightGBM batch scoring + ensemble gate for live screener path."""

from __future__ import annotations

import json
import pickle
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "artifacts"
MODEL_PATH = ROOT / "models" / "latest_lgbm_ranker.pkl"
METRICS_PATH = ART / "model_metrics.json"
REGISTRY_PATH = ART / "model_registry.json"
LEAKAGE_PATH = ART / "leakage_test_report.json"
WIDE_PATH = ROOT / "data" / "parquet" / "features" / "alpha158" / "alpha158_wide.parquet"

_GATE_CACHE: dict[str, Any] | None = None


@lru_cache(maxsize=1)
def _feature_columns() -> tuple[str, ...]:
    if MODEL_PATH.exists():
        try:
            with MODEL_PATH.open("rb") as f:
                blob = pickle.load(f)
            feats = blob.get("features")
            if feats:
                return tuple(feats)
        except Exception:
            pass
    from quant.features.alpha158 import feature_column_names

    return tuple(feature_column_names())


def get_ml_gate_status() -> dict[str, Any]:
    """Whether LGBM ensemble is allowed (auto-degrade to baseline otherwise)."""
    global _GATE_CACHE
    if _GATE_CACHE is not None:
        return _GATE_CACHE

    metrics: dict[str, Any] = {}
    registry: dict[str, Any] = {}
    leakage: dict[str, Any] = {}
    if METRICS_PATH.exists():
        metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    if REGISTRY_PATH.exists():
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    if LEAKAGE_PATH.exists():
        leakage = json.loads(LEAKAGE_PATH.read_text(encoding="utf-8"))

    ric = metrics.get("rank_ic_oos") or metrics.get("rank_ic") or {}
    reasons: list[str] = []
    passed = True

    if not MODEL_PATH.exists():
        passed = False
        reasons.append("model_file_missing")
    if registry.get("status") == "REJECTED":
        passed = False
        reasons.append("registry_rejected")
    if not metrics.get("train", {}).get("trained"):
        passed = False
        reasons.append("model_not_trained")
    if leakage and not leakage.get("passed", True):
        passed = False
        reasons.append("leakage_test_failed")
    if float(ric.get("mean_rank_ic") or 0) < 0.015:
        passed = False
        reasons.append("rank_ic_below_threshold")
    if float(ric.get("icir") or 0) < 0.20:
        passed = False
        reasons.append("icir_below_threshold")

    _GATE_CACHE = {
        "passed": passed,
        "mode": "ensemble_lgbm" if passed else "baseline_fallback",
        "reasons": reasons,
        "model_id": registry.get("model_id"),
        "rank_ic_oos": ric,
        "weights": {"ml": 0.45, "baseline": 0.35, "risk": 0.20},
    }
    return _GATE_CACHE


def invalidate_gate_cache() -> None:
    global _GATE_CACHE
    _GATE_CACHE = None
    _feature_columns.cache_clear()


def predict_ml_batch(symbols: list[str], as_of_date: str | None = None) -> dict[str, float]:
    """Alpha158 → LightGBM raw scores for symbols (cache + on-the-fly fallback)."""
    from quant.models.lgbm_ranker import predict_ranker

    if not symbols or not MODEL_PATH.exists():
        return {}

    feat_cols = list(_feature_columns())
    feat_map = _load_feature_matrix(symbols, as_of_date, feat_cols)
    if not feat_map:
        return {}

    ordered = [s for s in symbols if s in feat_map]
    X = [[float(feat_map[s].get(c) or 0.0) for c in feat_cols] for s in ordered]
    preds = predict_ranker(X)
    if not preds:
        return {}
    return {s: float(p) for s, p in zip(ordered, preds)}


def _load_feature_matrix(
    symbols: list[str],
    as_of_date: str | None,
    feat_cols: list[str],
) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    if WIDE_PATH.exists():
        import pandas as pd

        wide = pd.read_parquet(WIDE_PATH, columns=["ts_code", "trade_date"] + [c for c in feat_cols if c])
        wide = wide[wide["ts_code"].isin(symbols)]
        if as_of_date:
            wide = wide[wide["trade_date"].astype(str) <= str(as_of_date)]
        if not wide.empty:
            wide = wide.sort_values("trade_date").groupby("ts_code", as_index=False).tail(1)
            for row in wide.itertuples(index=False):
                sym = row.ts_code
                out[sym] = {c: getattr(row, c, 0.0) for c in feat_cols if hasattr(row, c)}

    missing = [s for s in symbols if s not in out]
    if missing and len(missing) <= 400:
        out.update(_compute_features_on_the_fly(missing, as_of_date, feat_cols))
    return out


def _compute_features_on_the_fly(
    symbols: list[str],
    as_of_date: str | None,
    feat_cols: list[str],
) -> dict[str, dict[str, float]]:
    import duckdb
    import pandas as pd

    from quant.features.alpha158 import compute_alpha158_frame

    wh = ROOT / "data" / "warehouse" / "quant.duckdb"
    if not wh.exists():
        return {}
    ph = ",".join(["?"] * len(symbols))
    date_filter = "AND trade_date <= ?" if as_of_date else ""
    params: list[Any] = list(symbols) + ([as_of_date] if as_of_date else [])
    con = duckdb.connect(str(wh), read_only=True)
    bars = con.execute(
        f"""
        SELECT ts_code, trade_date, open, high, low, close, vol, amount
        FROM daily_bars
        WHERE ts_code IN ({ph}) {date_filter}
        ORDER BY ts_code, trade_date
        """,
        params,
    ).fetchdf()
    con.close()
    if bars.empty:
        return {}

    frame = compute_alpha158_frame(bars)
    if frame.empty:
        return {}
    if as_of_date:
        frame = frame[frame["trade_date"].astype(str) <= str(as_of_date)]
    frame = frame.sort_values("trade_date").groupby("ts_code", as_index=False).tail(1)
    result: dict[str, dict[str, float]] = {}
    for row in frame.itertuples(index=False):
        result[row.ts_code] = {c: float(getattr(row, c, 0) or 0) for c in feat_cols if hasattr(row, c)}
    return result


def apply_ensemble_to_rows(
    raw: list[dict[str, Any]],
    *,
    as_of_date: str | None,
    z: dict[str, dict[str, float]],
    mode: str = "eod",
    fast: bool = False,
    ml_top_n: int = 200,
) -> dict[str, Any]:
    """Replace row scores with 45/35/20 ensemble or baseline fallback."""
    from quant.models.ensemble import ensemble_score

    gate = get_ml_gate_status()
    baseline = {r["symbol"]: float(r.get("baseline_score", r.get("score", 0))) for r in raw}
    risk = {r["symbol"]: -float(z.get("vol_20", {}).get(r["symbol"], 0)) for r in raw}
    ml: dict[str, float] | None = None
    if gate["passed"] and not fast:
        ranked = sorted(raw, key=lambda r: baseline.get(r["symbol"], 0), reverse=True)
        ml_syms = [r["symbol"] for r in ranked[: max(50, ml_top_n)]]
        ml = predict_ml_batch(ml_syms, as_of_date)
    elif fast:
        gate = {**gate, "mode": "baseline_fast", "passed": False, "reasons": list(gate.get("reasons") or []) + ["fast_path"]}

    final = ensemble_score(baseline, ml, risk, ml_passed=bool(ml))
    live_modes = ("live", "realtime", "intraday")
    for r in raw:
        sym = r["symbol"]
        ens = float(final.get(sym, baseline.get(sym, 0)))
        live_comp = float(r.get("live_score_component") or 0)
        if mode.lower() in live_modes and live_comp:
            r["score"] = 0.45 * ens + live_comp
        else:
            r["score"] = ens
        r["ensemble_score"] = ens
        r["ml_score"] = (ml or {}).get(sym)
        r["ensemble_mode"] = gate["mode"]

    return gate
