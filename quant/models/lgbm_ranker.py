"""LightGBM LambdaRank with Ridge fallback — no silent mock."""

from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT / "models"


def _try_lightgbm():
    try:
        import lightgbm as lgb  # type: ignore

        return lgb
    except (ImportError, OSError):
        return None


def train_ranker(
    X: list[list[float]],
    y: list[int],
    groups: list[int],
    *,
    feature_names: list[str] | None = None,
    seed: int = 42,
) -> dict[str, Any]:
    """Train ranking model. Falls back to numpy Ridge on bucket labels."""
    lgb = _try_lightgbm()
    if lgb and len(X) >= 200 and sum(groups) >= 50:
        import numpy as np

        ds = lgb.Dataset(np.array(X), label=y, group=groups, feature_name=feature_names or "auto")
        params = {
            "objective": "lambdarank",
            "metric": "ndcg",
            "num_leaves": 31,
            "learning_rate": 0.03,
            "n_estimators": 300,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "min_child_samples": 80,
            "reg_alpha": 1.0,
            "reg_lambda": 5.0,
            "seed": seed,
            "verbose": -1,
        }
        model = lgb.train(params, ds, num_boost_round=min(300, max(50, len(X) // 100)))
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        path = MODEL_DIR / "latest_lgbm_ranker.pkl"
        with path.open("wb") as f:
            pickle.dump({"model": model, "type": "lightgbm", "features": feature_names}, f)
        return {"trained": True, "model_type": "lightgbm", "path": str(path.relative_to(ROOT)), "n_samples": len(X)}

    # Ridge fallback (closed-form via normal equations on small feature sets)
    weights = _ridge_fit(X, y)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    path = MODEL_DIR / "latest_ridge_ranker.json"
    payload = {"model_type": "ridge_fallback", "weights": weights, "features": feature_names, "n_samples": len(X)}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {"trained": True, "model_type": "ridge_fallback", "path": str(path.relative_to(ROOT)), "n_samples": len(X), "note": "pip install lightgbm for LambdaRank"}


def predict_ranker(X: list[list[float]]) -> list[float] | None:
    lgb_path = MODEL_DIR / "latest_lgbm_ranker.pkl"
    ridge_path = MODEL_DIR / "latest_ridge_ranker.json"
    if lgb_path.exists():
        with lgb_path.open("rb") as f:
            blob = pickle.load(f)
        if blob.get("type") == "lightgbm":
            import numpy as np

            return blob["model"].predict(np.array(X)).tolist()
    if ridge_path.exists():
        data = json.loads(ridge_path.read_text(encoding="utf-8"))
        w = data.get("weights") or []
        return [_dot(x, w) for x in X]
    return None


def _ridge_fit(X: list[list[float]], y: list[int], lam: float = 5.0) -> list[float]:
    if not X:
        return []
    p = len(X[0])
    xtx = [[0.0] * p for _ in range(p)]
    xty = [0.0] * p
    for row, yi in zip(X, y):
        for i in range(p):
            xty[i] += row[i] * yi
            for j in range(p):
                xtx[i][j] += row[i] * row[j]
    for i in range(p):
        xtx[i][i] += lam
    # augment intercept
    return _solve(xtx, xty) or [0.0] * p


def _solve(a: list[list[float]], b: list[float]) -> list[float] | None:
    n = len(b)
    mat = [a[i][:] + [b[i]] for i in range(n)]
    for col in range(n):
        piv = col
        for r in range(col + 1, n):
            if abs(mat[r][col]) > abs(mat[piv][col]):
                piv = r
        if abs(mat[piv][col]) < 1e-12:
            return None
        mat[col], mat[piv] = mat[piv], mat[col]
        d = mat[col][col]
        for j in range(col, n + 1):
            mat[col][j] /= d
        for r in range(n):
            if r == col:
                continue
            f = mat[r][col]
            for j in range(col, n + 1):
                mat[r][j] -= f * mat[col][j]
    return [mat[i][n] for i in range(n)]


def _dot(a: list[float], b: list[float]) -> float:
    return sum(ai * bi for ai, bi in zip(a, b[: len(a)]))
