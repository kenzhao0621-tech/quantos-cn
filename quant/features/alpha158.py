"""Alpha158-compatible feature engine (Qlib-inspired, 158 columns).

Reference: Microsoft Qlib `Alpha158` handler — we implement the same *formula families*
without requiring native qlib. NOT identical to qlib's internal Cython path; versioned
as alpha158_compatible_v1 for reproducibility.
"""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

FEATURE_VERSION = "alpha158_compatible_v1"
WINDOWS: tuple[int, ...] = (5, 10, 20, 30, 60)

# Rolling operator suffixes aligned with Qlib Alpha158 naming (subset + extensions → 158 cols)
ROLL_OPS: tuple[str, ...] = (
    "ROC", "MA", "STD", "MAX", "MIN", "RSV", "CORR", "CORD", "VMA", "VSTD",
    "BETA", "RSQR", "QTLU", "QTLD", "RANK", "IMAX", "IMIN", "CNTP", "CNTN", "SUMD",
    "WVMA", "VSUMP", "VSUMN", "IMXD", "CNTD",
)


def feature_column_names() -> list[str]:
    """Return ordered 158 feature column names."""
    names: list[str] = list(KBAR_NAMES)
    for w in WINDOWS:
        for op in ROLL_OPS:
            names.append(f"{op}{w}")
    # pad to 158 with extra volume-price ratios if needed
    extras = [
        "RET1", "RET5", "RET10", "RET20", "RET60",
        "VOLUME0", "AMOUNT0", "VWAP0", "KMID3", "RANGE0", "BODY0",
        "VOLAT5", "VOLAT20", "GAP0", "SHADOW0", "UPPER0",
        "LOWER0", "MID0", "TREND5", "TREND20", "AMIHUD20", "TURN20",
        "HL2", "OC2",
    ]
    for e in extras:
        if len(names) < 158:
            names.append(e)
    return names[:158]


KBAR_NAMES: tuple[str, ...] = (
    "KMID",
    "KLEN",
    "KMID2",
    "KUP",
    "KUP2",
    "KLOW",
    "KLOW2",
    "KSFT",
    "KSFT2",
)


def _kbar_features(o: pd.Series, h: pd.Series, l: pd.Series, c: pd.Series) -> pd.DataFrame:
    """Single-bar candle ratios (9 features)."""
    hl = (h - l).replace(0, np.nan)
    oc_max = pd.concat([o, c], axis=1).max(axis=1)
    oc_min = pd.concat([o, c], axis=1).min(axis=1)
    out = pd.DataFrame(index=c.index)
    out["KMID"] = (c - o) / hl
    out["KLEN"] = hl / c.replace(0, np.nan)
    out["KMID2"] = (c - o) / c.replace(0, np.nan)
    out["KUP"] = (h - oc_max) / hl
    out["KUP2"] = (h - oc_max) / c.replace(0, np.nan)
    out["KLOW"] = (oc_min - l) / hl
    out["KLOW2"] = (oc_min - l) / c.replace(0, np.nan)
    out["KSFT"] = (2 * c - h - l) / hl
    out["KSFT2"] = (2 * c - h - l) / c.replace(0, np.nan)
    return out


def _rolling_features(g: pd.DataFrame) -> pd.DataFrame:
    """Compute rolling features for one symbol group (sorted by trade_date)."""
    o = g["open"].astype(float)
    h = g["high"].astype(float)
    l = g["low"].astype(float)
    c = g["close"].astype(float)
    v = g["vol"].astype(float).replace(0, np.nan)
    amt = g["amount"].astype(float) if "amount" in g else v
    ret = c.pct_change()
    log_v = np.log(v + 1.0)

    parts = [_kbar_features(o, h, l, c)]
    for w in WINDOWS:
        roc = c.shift(w) / c - 1.0
        ma = c.rolling(w).mean() / c - 1.0
        std = ret.rolling(w).std()
        mx = h.rolling(w).max() / c - 1.0
        mn = l.rolling(w).min() / c - 1.0
        rmin = l.rolling(w).min()
        rmax = h.rolling(w).max()
        rsv = (c - rmin) / (rmax - rmin).replace(0, np.nan)
        corr = ret.rolling(w).corr(log_v.pct_change())
        cord = c.pct_change().rolling(w).corr(log_v.diff())
        vma = v / v.rolling(w).mean() - 1.0
        vstd = log_v.rolling(w).std()
        beta = ret.rolling(w).cov(c.pct_change()) / (c.pct_change().rolling(w).var().replace(0, np.nan))
        rsqr = ret.rolling(w).apply(lambda x: x.autocorr(lag=1) ** 2 if len(x) > 2 else np.nan, raw=False)
        qtlu = c.rolling(w).quantile(0.8) / c - 1.0
        qtld = c.rolling(w).quantile(0.2) / c - 1.0
        rank = c.rolling(w).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1] if len(x) else np.nan, raw=False)
        imax = h.rolling(w).apply(lambda x: float(np.argmax(x)) / w if len(x) else np.nan, raw=False)
        imin = l.rolling(w).apply(lambda x: float(np.argmin(x)) / w if len(x) else np.nan, raw=False)
        cntp = (ret > 0).rolling(w).mean()
        cntn = (ret < 0).rolling(w).mean()
        sumd = ret.rolling(w).sum()
        wvma = (ret.abs() * v).rolling(w).sum() / (v.rolling(w).sum().replace(0, np.nan))
        vsump = v.where(ret > 0, 0).rolling(w).sum() / v.rolling(w).sum().replace(0, np.nan)
        vsumn = v.where(ret < 0, 0).rolling(w).sum() / v.rolling(w).sum().replace(0, np.nan)
        imxd = imax - imin
        cntd = cntp - cntn

        parts.append(
            pd.DataFrame(
                {
                    f"ROC{w}": roc,
                    f"MA{w}": ma,
                    f"STD{w}": std,
                    f"MAX{w}": mx,
                    f"MIN{w}": mn,
                    f"RSV{w}": rsv,
                    f"CORR{w}": corr,
                    f"CORD{w}": cord,
                    f"VMA{w}": vma,
                    f"VSTD{w}": vstd,
                    f"BETA{w}": beta,
                    f"RSQR{w}": rsqr,
                    f"QTLU{w}": qtlu,
                    f"QTLD{w}": qtld,
                    f"RANK{w}": rank,
                    f"IMAX{w}": imax,
                    f"IMIN{w}": imin,
                    f"CNTP{w}": cntp,
                    f"CNTN{w}": cntn,
                    f"SUMD{w}": sumd,
                    f"WVMA{w}": wvma,
                    f"VSUMP{w}": vsump,
                    f"VSUMN{w}": vsumn,
                    f"IMXD{w}": imxd,
                    f"CNTD{w}": cntd,
                },
                index=g.index,
            )
        )

    feat = pd.concat(parts, axis=1)
    feat["RET1"] = ret
    feat["RET5"] = c / c.shift(5) - 1.0
    feat["RET10"] = c / c.shift(10) - 1.0
    feat["RET20"] = c / c.shift(20) - 1.0
    feat["RET60"] = c / c.shift(60) - 1.0
    feat["VOLUME0"] = log_v
    feat["AMOUNT0"] = np.log(amt.astype(float) + 1.0)
    feat["VWAP0"] = amt / v.replace(0, np.nan) / c.replace(0, np.nan)
    feat["KMID3"] = (c - o) / o.replace(0, np.nan)
    feat["RANGE0"] = (h - l) / c.replace(0, np.nan)
    feat["BODY0"] = (c - o).abs() / c.replace(0, np.nan)
    feat["VOLAT5"] = ret.rolling(5).std()
    feat["VOLAT20"] = ret.rolling(20).std()
    feat["GAP0"] = o / c.shift(1) - 1.0
    feat["SHADOW0"] = ((h - l) - (c - o).abs()) / c.replace(0, np.nan)
    feat["UPPER0"] = (h - pd.concat([o, c], axis=1).max(axis=1)) / c.replace(0, np.nan)
    oc_min = pd.concat([o, c], axis=1).min(axis=1)
    feat["LOWER0"] = (oc_min - l) / c.replace(0, np.nan)
    feat["MID0"] = ((h + l) / 2) / c.replace(0, np.nan)
    feat["HL2"] = (h + l) / 2
    feat["OC2"] = (o + c) / 2
    feat["TREND5"] = c / c.rolling(5).mean() - 1.0
    feat["TREND20"] = c / c.rolling(20).mean() - 1.0
    feat["AMIHUD20"] = (ret.abs() / amt.replace(0, np.nan)).rolling(20).mean()
    feat["TURN20"] = v / v.rolling(20).mean()

    cols = feature_column_names()
    for col in cols:
        if col not in feat.columns:
            feat[col] = np.nan
    return feat[cols]


def compute_alpha158_frame(bars: pd.DataFrame) -> pd.DataFrame:
    """Wide Alpha158 frame with ts_code, trade_date + 158 features."""
    df = bars.copy()
    if "ts_code" not in df.columns and "symbol" in df.columns:
        df["ts_code"] = df["symbol"]
    df["trade_date"] = df["trade_date"].astype(str)
    df = df.sort_values(["ts_code", "trade_date"])
    chunks: list[pd.DataFrame] = []
    for sym, g in df.groupby("ts_code", sort=False):
        if len(g) < max(WINDOWS) + 5:
            continue
        feats = _rolling_features(g)
        block = pd.concat(
            [g[["ts_code", "trade_date"]].reset_index(drop=True), feats.reset_index(drop=True)],
            axis=1,
        )
        chunks.append(block)
    if not chunks:
        return pd.DataFrame(columns=["ts_code", "trade_date"] + feature_column_names())
    out = pd.concat(chunks, ignore_index=True)
    return out.replace([np.inf, -np.inf], np.nan)


def winsorize_frame(feat: pd.DataFrame, cols: Iterable[str], lower: float = 0.01, upper: float = 0.99) -> pd.DataFrame:
    """Cross-section winsorize per trade_date."""
    out = feat.copy()
    for d, idx in out.groupby("trade_date").groups.items():
        for col in cols:
            s = out.loc[idx, col]
            clean = s.dropna()
            if len(clean) < 10:
                continue
            lo, hi = clean.quantile(lower), clean.quantile(upper)
            out.loc[idx, col] = s.clip(lo, hi)
    return out
