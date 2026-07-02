"""KronosSignalProvider — distribution forecasts with honest degradation.

Contract (refactor prompt §6.2):
- predict_distribution() returns paths/expected_return/volatility/downside_risk/
  confidence plus degraded flag + reason.
- generate_signal() normalises to score [-1, 1] with risk penalty and explanation.
- Kronos never decides trades alone — the signal is one input to the ensemble.

Degraded path: if the sidecar venv / model / vendor repo is unavailable or the
call fails, a bootstrap Monte Carlo over the symbol's own historical returns is
used and the output is explicitly labeled degraded (never silent).
"""

from __future__ import annotations

import json
import random
import statistics
import subprocess
from typing import Any

from quant.models.kronos.config import (
    DEFAULT_HORIZON,
    DEFAULT_LOOKBACK,
    DEFAULT_MODEL,
    DEFAULT_N_PATHS,
    ROOT,
    SIDECAR_PYTHON,
    SIDECAR_SCRIPT,
    SIDECAR_TIMEOUT_SEC,
    sidecar_available,
)
from quant.models.kronos.data_adapter import bars_are_adjusted, load_ohlcv_bars


def _path_stats(paths: list[list[float]]) -> dict[str, float]:
    """Distribution stats over terminal returns of Monte Carlo paths."""
    terminal = [p[-1] for p in paths if p]
    if not terminal:
        return {"expected_return": 0.0, "volatility": 0.0, "downside_risk": 0.0, "confidence": 0.0}
    mean = statistics.fmean(terminal)
    vol = statistics.pstdev(terminal) if len(terminal) > 1 else 0.0
    downside = [r for r in terminal if r < 0]
    downside_risk = abs(statistics.fmean(downside)) if downside else 0.0
    agree = sum(1 for r in terminal if (r > 0) == (mean > 0)) / len(terminal)
    dispersion_penalty = min(1.0, vol / 0.10)
    confidence = round(max(0.0, min(1.0, agree * (1.0 - 0.5 * dispersion_penalty))), 3)
    return {
        "expected_return": round(mean, 5),
        "volatility": round(vol, 5),
        "downside_risk": round(downside_risk, 5),
        "confidence": confidence,
    }


class KronosSignalProvider:
    """Kronos-mini K-line distribution forecaster with statistical fallback."""

    def __init__(self, model: str = DEFAULT_MODEL, *, n_paths: int = DEFAULT_N_PATHS,
                 timeout_sec: int = SIDECAR_TIMEOUT_SEC) -> None:
        self.model = model
        self.n_paths = n_paths
        self.timeout_sec = timeout_sec

    def fit(self, train_data: Any = None, valid_data: Any = None) -> None:
        """Inference-only integration — no default training (refactor prompt §1.1)."""
        return None

    # ------------------------------------------------------------------ #

    def predict_distribution(self, symbol: str, lookback_df: list[dict[str, Any]] | None = None,
                             horizon: int = DEFAULT_HORIZON, *, as_of_date: str | None = None) -> dict[str, Any]:
        bars = lookback_df if lookback_df is not None else load_ohlcv_bars(
            symbol, lookback=DEFAULT_LOOKBACK, as_of_date=as_of_date,
        )
        base: dict[str, Any] = {
            "symbol": symbol,
            "horizon": horizon,
            "model": self.model,
            "price_adjusted": bars_are_adjusted(),
        }
        if len(bars) < 30:
            return {**base, "paths": [], "expected_return": 0.0, "volatility": 0.0,
                    "downside_risk": 0.0, "confidence": 0.0, "degraded": True,
                    "reason": f"insufficient_history:{len(bars)}_bars"}

        ok, reason = sidecar_available()
        if ok:
            result = self._call_sidecar(bars, horizon)
            if result.get("ok"):
                stats = _path_stats(result["paths"])
                return {**base, "paths": result["paths"], **stats,
                        "degraded": False, "reason": "",
                        "device": result.get("device"),
                        "lookback_used": result.get("lookback_used"),
                        "elapsed_ms": result.get("elapsed_ms")}
            reason = str(result.get("error") or "sidecar_failed")

        fallback = self._bootstrap_fallback(bars, horizon)
        stats = _path_stats(fallback)
        # Fallback confidence is capped — it is NOT a model forecast.
        stats["confidence"] = round(min(stats["confidence"], 0.35), 3)
        return {**base, "paths": fallback, **stats, "degraded": True,
                "reason": f"kronos_unavailable:{reason};bootstrap_mc_fallback"}

    def generate_signal(self, prediction: dict[str, Any]) -> dict[str, Any]:
        er = float(prediction.get("expected_return") or 0.0)
        vol = float(prediction.get("volatility") or 0.0)
        downside = float(prediction.get("downside_risk") or 0.0)
        conf = float(prediction.get("confidence") or 0.0)
        degraded = bool(prediction.get("degraded"))

        # Scale: ±5% expected horizon return maps to score ±1.
        raw = max(-1.0, min(1.0, er / 0.05))
        risk_penalty = round(min(1.0, downside / 0.05 * 0.5 + vol / 0.10 * 0.5), 3)
        score = round(raw * (1.0 - 0.5 * risk_penalty), 3)

        horizon = prediction.get("horizon")
        src = "Kronos-mini 分布预测" if not degraded else "统计降级路径（bootstrap，非模型预测）"
        explanation = (
            f"{src}：{horizon} 日预期收益 {er * 100:.2f}%（路径波动 {vol * 100:.2f}%，"
            f"下行风险 {downside * 100:.2f}%，置信 {conf:.2f}）。仅供研究，不构成投资建议。"
        )
        return {
            "symbol": prediction.get("symbol"),
            "score": score,
            "rank_score": round(raw, 3),
            "confidence": conf,
            "risk_penalty": risk_penalty,
            "explanation": explanation,
            "degraded": degraded,
            "model": prediction.get("model"),
        }

    # ------------------------------------------------------------------ #

    def _call_sidecar(self, bars: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
        payload = json.dumps({
            "bars": bars, "horizon": horizon, "n_paths": self.n_paths,
            "model": self.model, "temperature": 0.7,
        })
        try:
            proc = subprocess.run(
                [str(SIDECAR_PYTHON), str(SIDECAR_SCRIPT)],
                input=payload, capture_output=True, text=True,
                timeout=self.timeout_sec, cwd=str(ROOT),
            )
            line = (proc.stdout or "").strip().splitlines()
            if not line:
                return {"ok": False, "error": f"empty_sidecar_output rc={proc.returncode} err={(proc.stderr or '')[-200:]}"}
            return json.loads(line[-1])
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": f"sidecar_timeout_{self.timeout_sec}s"}
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    def _bootstrap_fallback(self, bars: list[dict[str, Any]], horizon: int) -> list[list[float]]:
        closes = [float(b["close"]) for b in bars if b.get("close")]
        rets = [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))]
        if not rets:
            return []
        rng = random.Random(42)
        paths: list[list[float]] = []
        for _ in range(self.n_paths):
            cum = 0.0
            path = []
            for _ in range(horizon):
                cum = (1 + cum) * (1 + rng.choice(rets)) - 1
                path.append(round(cum, 5))
            paths.append(path)
        return paths
