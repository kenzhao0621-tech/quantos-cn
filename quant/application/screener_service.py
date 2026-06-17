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
        }


@dataclass
class ScreenResult:
    as_of_date: Optional[str]
    preset: str
    universe_size: int
    candidates: list[Candidate]
    blocked: bool = False
    blocker_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "as_of_date": self.as_of_date,
            "preset": self.preset,
            "universe_size": self.universe_size,
            "candidates": [c.to_dict() for c in self.candidates],
            "blocked": self.blocked,
            "blocker_reason": self.blocker_reason,
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

        con = duckdb.connect(str(self.warehouse), read_only=True)
        as_of = con.execute("SELECT max(trade_date) FROM daily_bars").fetchone()[0]
        as_of_str = str(as_of) if as_of else None

        rows = con.execute(
            """
            WITH recent AS (
                SELECT ts_code, trade_date, close, pct_chg, amount,
                       row_number() OVER (PARTITION BY ts_code ORDER BY trade_date DESC) AS rn
                FROM daily_bars
                WHERE trade_date >= (SELECT max(trade_date) - INTERVAL 110 DAY FROM daily_bars)
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
            """
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
            raw.append({
                "symbol": ts_code,
                "last_close": float(last_close),
                "last_pct": float(last_pct or 0.0),
                "ret_20": float(last_close) / float(c20) - 1.0,
                "ret_60": float(last_close) / float(c60) - 1.0,
                "trend": float(last_close) / float(ma20) - 1.0,
                "vol_20": float(vol20 or 0.0),
                "avg_amount": avg_amount_yuan,
            })

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
        for r in raw:
            sym = r["symbol"]
            r["score"] = (
                weights["ret_20"] * z["ret_20"][sym]
                + weights["ret_60"] * z["ret_60"][sym]
                + weights["trend"] * z["trend"][sym]
                - weights["vol_penalty"] * z["vol_20"][sym]
            )

        raw.sort(key=lambda r: r["score"], reverse=True)
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
            )
            for i, r in enumerate(top)
        ]
        return ScreenResult(as_of_str, preset, universe, candidates)


def _is_main_board(ts_code: str) -> bool:
    code = ts_code.split(".")[0]
    # Keep SH main (60), SZ main (00), ChiNext (30), STAR (688). Drop BSE (8/4) etc.
    return code.startswith(("60", "00", "30", "688"))


_service: Optional[ScreenerService] = None


def get_screener_service() -> ScreenerService:
    global _service
    if _service is None:
        _service = ScreenerService()
    return _service
