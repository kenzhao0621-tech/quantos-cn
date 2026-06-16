"""Model trial registry and anti-overfitting metrics."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from gateway.config import ROOT


@dataclass
class ModelTrial:
    trial_id: str
    model_id: str
    strategy_id: str
    created_at: str
    status: str  # RUNNING | PASSED | FAILED | REJECTED
    sharpe: float | None = None
    deflated_sharpe: float | None = None
    pbo: float | None = None
    notes: str = ""
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TrialRegistry:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or ROOT / "data" / "gateway" / "model_trials.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def register(self, model_id: str, strategy_id: str, params: dict[str, Any] | None = None) -> ModelTrial:
        trial = ModelTrial(
            trial_id=str(uuid4()),
            model_id=model_id,
            strategy_id=strategy_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            status="RUNNING",
            params=params or {},
        )
        self._append(trial)
        return trial

    def complete(
        self,
        trial: ModelTrial,
        *,
        sharpe: float,
        num_trials: int,
        skew: float = 0.0,
        kurtosis: float = 3.0,
    ) -> ModelTrial:
        trial.sharpe = sharpe
        trial.deflated_sharpe = deflated_sharpe_ratio(sharpe, num_trials, skew, kurtosis)
        trial.pbo = probability_backtest_overfitting(sharpe, num_trials)
        if trial.deflated_sharpe is not None and trial.deflated_sharpe < 0:
            trial.status = "REJECTED"
            trial.notes = "deflated_sharpe_negative"
        elif trial.pbo is not None and trial.pbo > 0.5:
            trial.status = "REJECTED"
            trial.notes = "pbo_too_high"
        else:
            trial.status = "PASSED"
        self._append(trial)
        return trial

    def list_trials(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def _append(self, trial: ModelTrial) -> None:
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(trial.to_dict(), ensure_ascii=False) + "\n")


def deflated_sharpe_ratio(sharpe: float, num_trials: int, skew: float = 0.0, kurtosis: float = 3.0) -> float:
    """Simplified Deflated Sharpe approximation for registry gating."""
    if num_trials <= 1:
        return sharpe
    euler = 0.5772156649
    expected_max = (1 - euler) * _inv_cdf(1 - 1 / num_trials) + euler * _inv_cdf(1 - 1 / (num_trials * math.e))
    penalty = expected_max * (1 + (1 - skew) / 6 * sharpe - (kurtosis - 3) / 24 * sharpe ** 2) ** -0.5
    return sharpe - penalty


def _inv_cdf(p: float) -> float:
    # rational approximation for standard normal inverse CDF
    if p <= 0 or p >= 1:
        return 0.0
    t = (-2 * math.log(min(p, 1 - p))) ** 0.5
    c0, c1, c2 = 2.515517, 0.802853, 0.010328
    d1, d2, d3 = 1.432788, 0.189269, 0.001308
    num = c0 + c1 * t + c2 * t * t
    den = 1 + d1 * t + d2 * t * t + d3 * t * t * t
    sign = 1 if p > 0.5 else -1
    return sign * (t - num / den)


def probability_backtest_overfitting(best_sharpe: float, num_trials: int) -> float:
    """Heuristic PBO proxy — higher when many trials chase one best Sharpe."""
    if num_trials <= 1:
        return 0.0
    return min(0.95, max(0.0, 1.0 - best_sharpe / (math.log(num_trials + 1) + 1e-6)))
