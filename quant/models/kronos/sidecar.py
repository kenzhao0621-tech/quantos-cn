"""Kronos sidecar — runs inside .venv-kronos (Python 3.10+), NOT the main venv.

Protocol: one JSON request on stdin → one JSON response on stdout.

Request:
    {"bars": [{"open":..,"high":..,"low":..,"close":..,"volume":..,"amount":..,
               "timestamp": "YYYY-MM-DD"}, ...],
     "horizon": 5, "n_paths": 30, "model": "kronos-mini", "temperature": 0.7}

Response (success):
    {"ok": true, "model": "kronos-mini", "paths": [[r1..rH], ...],
     "pred_closes": [[c1..cH], ...], "elapsed_ms": ...}
Response (failure):
    {"ok": false, "error": "..."}
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
VENDOR = ROOT / "vendor" / "kronos"

MODEL_REPOS = {
    "kronos-mini": ("NeoQuasar/Kronos-mini", "NeoQuasar/Kronos-Tokenizer-2k", 2048),
    "kronos-small": ("NeoQuasar/Kronos-small", "NeoQuasar/Kronos-Tokenizer-base", 512),
}


def main() -> int:
    start = time.perf_counter()
    try:
        req = json.loads(sys.stdin.read())
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"bad_request: {exc}"}))
        return 1

    try:
        sys.path.insert(0, str(VENDOR))
        import pandas as pd
        import torch
        from model import Kronos, KronosPredictor, KronosTokenizer

        model_name = req.get("model") or "kronos-mini"
        repo, tok_repo, max_ctx = MODEL_REPOS[model_name]
        horizon = int(req.get("horizon") or 5)
        n_paths = max(1, min(int(req.get("n_paths") or 30), 100))
        temperature = float(req.get("temperature") or 0.7)

        bars = req["bars"]
        if len(bars) < 30:
            print(json.dumps({"ok": False, "error": f"insufficient_bars: {len(bars)}"}))
            return 1
        df = pd.DataFrame(bars)
        df["timestamps"] = pd.to_datetime(df["timestamp"])
        for col in ("open", "high", "low", "close"):
            df[col] = df[col].astype(float)
        df["volume"] = df.get("volume", 0).astype(float)
        df["amount"] = df.get("amount", 0).astype(float)
        lookback = min(len(df), max_ctx - horizon - 8)
        df = df.tail(lookback).reset_index(drop=True)

        device = "mps" if torch.backends.mps.is_available() else "cpu"
        tokenizer = KronosTokenizer.from_pretrained(tok_repo)
        model = Kronos.from_pretrained(repo)
        predictor = KronosPredictor(model, tokenizer, device=device, max_context=max_ctx)

        x_df = df[["open", "high", "low", "close", "volume", "amount"]]
        x_ts = df["timestamps"]
        freq = pd.tseries.frequencies.to_offset("B")
        y_ts = pd.Series(pd.date_range(start=x_ts.iloc[-1] + freq, periods=horizon, freq=freq))

        last_close = float(df["close"].iloc[-1])
        paths: list[list[float]] = []
        pred_closes: list[list[float]] = []
        # sample_count>1 inside predict averages samples; we need distinct paths,
        # so we call predict n_paths times with sampling temperature.
        for _ in range(n_paths):
            pred = predictor.predict(
                df=x_df, x_timestamp=x_ts, y_timestamp=y_ts,
                pred_len=horizon, T=temperature, top_p=0.9, sample_count=1,
                verbose=False,
            )
            closes = [float(c) for c in pred["close"].tolist()]
            pred_closes.append(closes)
            paths.append([c / last_close - 1.0 for c in closes])

        print(json.dumps({
            "ok": True,
            "model": model_name,
            "device": device,
            "lookback_used": lookback,
            "last_close": last_close,
            "paths": paths,
            "pred_closes": pred_closes,
            "elapsed_ms": round((time.perf_counter() - start) * 1000, 1),
        }))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
