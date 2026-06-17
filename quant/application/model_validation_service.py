"""Model validation service for production-readiness checks.

Runs out-of-sample and rolling validation on the real DuckDB daily_bars store.
The goal is to prevent one-day recommendations from being treated as deployable
signals without costs, slippage, execution constraints, and sample evidence.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
WAREHOUSE = ROOT / "data" / "warehouse" / "quant.duckdb"


@dataclass
class ValidationConfig:
    preset: str = "balanced"
    lookback_days: int = 45
    top_n: int = 10
    max_per_sector: int = 2
    cost_bps: float = 8.0
    slippage_bps: float = 12.0
    min_amount_cny: float = 100_000_000.0


@dataclass
class ValidationResult:
    config: dict[str, Any]
    sample: dict[str, Any]
    out_of_sample: dict[str, Any]
    rolling: dict[str, Any]
    factor_stability: dict[str, Any]
    execution: dict[str, Any]
    paper_shadow: dict[str, Any]
    verdict: str
    actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "config": self.config,
            "sample": self.sample,
            "out_of_sample": self.out_of_sample,
            "rolling": self.rolling,
            "factor_stability": self.factor_stability,
            "execution": self.execution,
            "paper_shadow": self.paper_shadow,
            "verdict": self.verdict,
            "actions": self.actions,
        }


class ModelValidationService:
    def __init__(self, warehouse: Path | None = None) -> None:
        self.warehouse = warehouse or WAREHOUSE

    def validate(self, config: ValidationConfig | None = None) -> ValidationResult:
        cfg = config or ValidationConfig()
        if not self.warehouse.exists():
            return ValidationResult(
                config=cfg.__dict__,
                sample={"blocked": True, "reason": "warehouse missing"},
                out_of_sample={},
                rolling={},
                factor_stability={},
                execution={},
                paper_shadow=_paper_shadow_stats(),
                verdict="BLOCKED_BY_DATA",
                actions=["先更新历史日线数据。"],
            )

        import duckdb
        from quant.application.screener_service import get_screener_service

        con = duckdb.connect(str(self.warehouse), read_only=True)
        dates = [str(x[0]) for x in con.execute("SELECT DISTINCT trade_date FROM daily_bars ORDER BY trade_date").fetchall()]
        if len(dates) < 70:
            con.close()
            return ValidationResult(
                config=cfg.__dict__,
                sample={"blocked": True, "trade_dates": len(dates), "reason": "not enough trade dates"},
                out_of_sample={},
                rolling={},
                factor_stability={},
                execution={},
                paper_shadow=_paper_shadow_stats(),
                verdict="BLOCKED_BY_DATA",
                actions=["至少需要约 70 个交易日用于样本外验证。"],
            )

        eval_dates = dates[-min(cfg.lookback_days + 1, len(dates) - 61):-1]
        svc = get_screener_service()
        daily_results: list[dict[str, Any]] = []
        prev_rank: dict[str, int] | None = None
        overlaps: list[float] = []

        for i, signal_date in enumerate(eval_dates):
            proof_date = dates[dates.index(signal_date) + 1]
            screen = svc.screen(
                preset=cfg.preset,
                top_n=100,
                min_amount_cny=cfg.min_amount_cny,
                as_of_date=signal_date,
                mode="eod",
            )
            selected = _sector_neutral_pick(screen.candidates, cfg.top_n, cfg.max_per_sector)
            if prev_rank is not None:
                curr_rank = {c.symbol: c.rank for c in screen.candidates[:100]}
                overlaps.append(_rank_overlap(prev_rank, curr_rank, k=30))
                prev_rank = curr_rank
            else:
                prev_rank = {c.symbol: c.rank for c in screen.candidates[:100]}
            if not selected:
                continue
            symbols = [c.symbol for c in selected]
            rows = _next_day_rows(con, signal_date, proof_date, symbols)
            bench = _benchmark_returns(con, signal_date, proof_date)
            proof_rows: list[dict[str, Any]] = []
            for c in selected:
                row = rows.get(c.symbol)
                if not row:
                    proof_rows.append({"symbol": c.symbol, "status": "SKIPPED_NO_NEXT_BAR"})
                    continue
                signal_close, next_open, next_high, next_low, next_close, next_pct = row
                buy_blocked = ((next_open / signal_close) - 1.0) * 100 >= 9.7
                sell_risk = float(next_pct or 0.0) <= -9.7
                gross = ((next_close / signal_close) - 1.0) * 100
                net = gross - (cfg.cost_bps + cfg.slippage_bps) / 100.0
                proof_rows.append({
                    "symbol": c.symbol,
                    "sector": c.sector,
                    "score": round(c.score, 3),
                    "gross_return": round(gross, 3),
                    "net_return": round(net, 3),
                    "benchmark_median": round(bench["median"], 3),
                    "excess": round(net - bench["median"], 3),
                    "buy_blocked_limit_up": buy_blocked,
                    "sell_limit_down_risk": sell_risk,
                    "status": "EXECUTABLE" if not buy_blocked else "BLOCKED_LIMIT_UP",
                })
            executable = [r for r in proof_rows if r.get("status") == "EXECUTABLE"]
            net_rets = [float(r["net_return"]) for r in executable]
            excess = [float(r["excess"]) for r in executable]
            daily_results.append({
                "signal_date": signal_date,
                "proof_date": proof_date,
                "count": len(proof_rows),
                "executable_count": len(executable),
                "avg_net_return": round(statistics.fmean(net_rets), 3) if net_rets else 0.0,
                "win_rate": round(sum(1 for x in net_rets if x > 0) / max(len(net_rets), 1) * 100, 1),
                "outperform_rate": round(sum(1 for x in excess if x > 0) / max(len(excess), 1) * 100, 1),
                "limit_blocked": sum(1 for r in proof_rows if r.get("buy_blocked_limit_up")),
                "limit_down_risk": sum(1 for r in proof_rows if r.get("sell_limit_down_risk")),
                "rows": proof_rows,
            })
        con.close()

        all_net = [r["avg_net_return"] for r in daily_results]
        oos_cut = max(1, int(len(daily_results) * 0.7))
        train = daily_results[:oos_cut]
        test = daily_results[oos_cut:]
        out = _summarize_days(test, label="out_of_sample")
        rolling = _summarize_days(daily_results, label="rolling")
        stability = {
            "top30_overlap_avg": round(statistics.fmean(overlaps) * 100, 1) if overlaps else 0.0,
            "interpretation": "过低说明每日换手过高，过高说明模型迟钝；30%-70%更健康。",
        }
        execution = {
            "cost_bps": cfg.cost_bps,
            "slippage_bps": cfg.slippage_bps,
            "limit_blocked_total": sum(d["limit_blocked"] for d in daily_results),
            "limit_down_risk_total": sum(d["limit_down_risk"] for d in daily_results),
            "sector_neutral_max_per_sector": cfg.max_per_sector,
        }
        sample = {
            "trade_dates_total": len(dates),
            "validation_days": len(daily_results),
            "train_days": len(train),
            "out_of_sample_days": len(test),
            "latest_data_date": dates[-1],
        }
        paper_shadow = _paper_shadow_stats()
        purged = _run_purged_kfold_validation(dates, daily_results, cfg)
        walk_forward = _run_walk_forward_validation(dates, daily_results)
        dsr_pbo = _dsr_pbo_metrics(all_net)
        verdict, actions = _verdict(out, rolling, stability, execution, paper_shadow, purged)
        result = ValidationResult(
            config=cfg.__dict__,
            sample=sample,
            out_of_sample={**out, **purged, **walk_forward, **dsr_pbo},
            rolling=rolling,
            factor_stability=stability,
            execution=execution,
            paper_shadow=paper_shadow,
            verdict=verdict,
            actions=actions,
        )
        _persist_validation(result, purged)
        return result


def _sector_neutral_pick(candidates: list[Any], top_n: int, max_per_sector: int) -> list[Any]:
    selected = []
    counts: dict[str, int] = {}
    for c in candidates:
        sec = c.sector or "UNKNOWN"
        if counts.get(sec, 0) >= max_per_sector:
            continue
        selected.append(c)
        counts[sec] = counts.get(sec, 0) + 1
        if len(selected) >= top_n:
            break
    return selected


def _next_day_rows(con: Any, signal_date: str, proof_date: str, symbols: list[str]) -> dict[str, tuple[float, float, float, float, float, float]]:
    if not symbols:
        return {}
    ph = ",".join(["?"] * len(symbols))
    rows = con.execute(
        f"""
        SELECT s.ts_code, s.close, p.open, p.high, p.low, p.close, p.pct_chg
        FROM daily_bars s JOIN daily_bars p ON p.ts_code = s.ts_code
        WHERE s.trade_date = ? AND p.trade_date = ? AND s.ts_code IN ({ph})
        """,
        [signal_date, proof_date, *symbols],
    ).fetchall()
    return {r[0]: tuple(float(x or 0) for x in r[1:]) for r in rows}


def _benchmark_returns(con: Any, signal_date: str, proof_date: str) -> dict[str, float]:
    rows = con.execute(
        """
        SELECT ((p.close / s.close) - 1.0) * 100
        FROM daily_bars s JOIN daily_bars p ON p.ts_code = s.ts_code
        WHERE s.trade_date = ? AND p.trade_date = ? AND s.close > 0
        """,
        [signal_date, proof_date],
    ).fetchall()
    vals = [float(x[0]) for x in rows if x[0] is not None]
    return {
        "mean": statistics.fmean(vals) if vals else 0.0,
        "median": statistics.median(vals) if vals else 0.0,
    }


def _rank_overlap(prev: dict[str, int], curr: dict[str, int], *, k: int) -> float:
    a = set(sorted(prev, key=prev.get)[:k])
    b = set(sorted(curr, key=curr.get)[:k])
    return len(a & b) / max(1, k)


def _summarize_days(days: list[dict[str, Any]], *, label: str) -> dict[str, Any]:
    vals = [float(d["avg_net_return"]) for d in days]
    wins = [float(d["win_rate"]) for d in days]
    out = [float(d["outperform_rate"]) for d in days]
    if not vals:
        return {"label": label, "days": 0, "blocked": True}
    downside = [x for x in vals if x < 0]
    return {
        "label": label,
        "days": len(days),
        "avg_daily_net_return": round(statistics.fmean(vals), 3),
        "median_daily_net_return": round(statistics.median(vals), 3),
        "positive_day_rate": round(sum(1 for x in vals if x > 0) / len(vals) * 100, 1),
        "avg_candidate_win_rate": round(statistics.fmean(wins), 1),
        "avg_outperform_rate": round(statistics.fmean(out), 1),
        "max_daily_loss": round(min(vals), 3),
        "downside_avg": round(statistics.fmean(downside), 3) if downside else 0.0,
    }


def _paper_shadow_stats() -> dict[str, Any]:
    paper_path = ROOT / "docs" / "ai" / "daily-trading" / "PAPER_SIGNAL_LEDGER.jsonl"
    shadow_path = ROOT / "data" / "gateway" / "shadow_orders.jsonl"
    paper = _count_jsonl(paper_path)
    shadow = _count_jsonl(shadow_path)
    return {
        "paper_records": paper["count"],
        "paper_recent": paper["recent"],
        "shadow_records": shadow["count"],
        "shadow_recent": shadow["recent"],
        "minimum_sample_required": 20,
        "sample_ready": (paper["count"] + shadow["count"]) >= 20,
    }


def _count_jsonl(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"count": 0, "recent": []}
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    return {"count": len(rows), "recent": rows[-5:]}


def _run_purged_kfold_validation(dates: list[str], daily_results: list[dict], cfg: ValidationConfig) -> dict[str, Any]:
    from quant.validation.purged_kfold import evaluate_screener_purged_kfold, purged_kfold_splits

    splits = purged_kfold_splits(dates, n_splits=5, train_size=40, test_size=5, purge_days=5, embargo_days=2)
    fold_returns: list[float] = []
    fold_hits: list[float] = []
    date_to_ret = {d["signal_date"]: d["avg_net_return"] for d in daily_results}
    for sp in splits:
        test_dates = [d for d in dates if sp["test_start"] <= d <= sp["test_end"]]
        rets = [date_to_ret[d] for d in test_dates if d in date_to_ret]
        if rets:
            fold_returns.append(statistics.fmean(rets))
            fold_hits.append(sum(1 for x in rets if x > 0) / len(rets))
    result = evaluate_screener_purged_kfold(fold_returns=fold_returns, fold_hit_rates=fold_hits)
    result["splits"] = len(splits)
    result["purged_kfold_passed"] = result.get("passed", False)
    return result


def _run_walk_forward_validation(dates: list[str], daily_results: list[dict]) -> dict[str, Any]:
    from quant.validation.overfitting import walk_forward_splits

    signal_dates = [d["signal_date"] for d in daily_results]
    if len(signal_dates) < 20:
        return {"walk_forward_passed": False, "walk_forward_folds": 0}
    splits = walk_forward_splits(signal_dates, train_size=max(10, len(signal_dates) // 2), test_size=5, step=3)
    wf_returns: list[float] = []
    date_to_ret = {d["signal_date"]: d["avg_net_return"] for d in daily_results}
    for sp in splits[:5]:
        test_dates = [d for d in signal_dates if sp["test_start"] <= d <= sp["test_end"]]
        rets = [date_to_ret[d] for d in test_dates if d in date_to_ret]
        if rets:
            wf_returns.append(statistics.fmean(rets))
    passed = bool(wf_returns) and statistics.fmean(wf_returns) > 0
    return {
        "walk_forward_folds": len(wf_returns),
        "walk_forward_mean_return": round(statistics.fmean(wf_returns), 3) if wf_returns else 0,
        "walk_forward_passed": passed,
    }


def _dsr_pbo_metrics(returns: list[float]) -> dict[str, Any]:
    if len(returns) < 5:
        return {"dsr": None, "pbo": None}
    try:
        from quant.validation.overfitting import deflated_sharpe_ratio, probability_backtest_overfitting

        mean = statistics.fmean(returns)
        std = statistics.pstdev(returns) if len(returns) > 1 else 1.0
        sharpe = (mean / std) * (252 ** 0.5) if std > 1e-9 else 0.0
        dsr_result = deflated_sharpe_ratio(sharpe, n_trials=3, n_obs=len(returns))
        pbo_result = probability_backtest_overfitting([returns])
        return {
            "dsr": dsr_result.get("dsr"),
            "dsr_passed": dsr_result.get("passed"),
            "pbo": pbo_result.get("pbo"),
            "pbo_passed": pbo_result.get("passed"),
        }
    except Exception:
        return {"dsr": None, "pbo": None}


def _persist_validation(result: ValidationResult, purged: dict[str, Any]) -> None:
    path = ROOT / "artifacts" / "model_validation.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = result.to_dict()
    payload["purged_kfold_passed"] = purged.get("purged_kfold_passed")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _verdict(
    out: dict[str, Any],
    rolling: dict[str, Any],
    stability: dict[str, Any],
    execution: dict[str, Any],
    paper: dict[str, Any],
    purged: dict[str, Any] | None = None,
) -> tuple[str, list[str]]:
    actions: list[str] = []
    if out.get("blocked"):
        return "BLOCKED_BY_DATA", ["没有足够样本外结果。"]
    if out.get("avg_daily_net_return", 0) <= 0:
        actions.append("样本外扣成本收益不达标，禁止进入真实交易。")
    if out.get("avg_outperform_rate", 0) < 52:
        actions.append("跑赢市场比例不足，需要复核因子权重或增加行业中性。")
    if execution.get("limit_blocked_total", 0) > 0:
        actions.append("存在涨停买入不可执行样本，实盘前必须过滤。")
    if stability.get("top30_overlap_avg", 0) < 20:
        actions.append("因子排名过于不稳定，可能过度追逐短期噪声。")
    if purged and not purged.get("purged_kfold_passed"):
        actions.append("Purged K-Fold 未通过，保持 RESEARCH_ONLY / Paper 阶段。")
    if not paper.get("sample_ready"):
        actions.append("Paper/Shadow 样本少于 20 条，不能升级真实交易流程。")
    if not actions and purged and purged.get("purged_kfold_passed"):
        return "PASS", ["验证通过，可进入扩展 Paper / Shadow。"]
    if not actions:
        return "CAUTION", ["继续扩展 Paper/Shadow 样本并每日复盘。"]
    return "NOT_READY", actions


_service: ModelValidationService | None = None


def get_model_validation_service() -> ModelValidationService:
    global _service
    if _service is None:
        _service = ModelValidationService()
    return _service

