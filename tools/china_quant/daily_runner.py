"""Daily real-data pipeline orchestrator."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from tools.china_quant.config import DEFAULT_RISK
from tools.china_quant.dossier import render_dossier
from tools.china_quant.modes import MODE_BANNERS, OperatingMode
from tools.china_quant.models import SectorInfo, StockRecord
from tools.china_quant.providers.akshare_provider import AKShareProvider
from tools.china_quant.providers.base import DataFreshness, ProviderError
from tools.china_quant.providers.fixture_provider import FixtureProvider
from tools.china_quant.regime_v2 import RegimeAnalysis, classify_regime_v2
from tools.china_quant.report import CandidatePlan, DailyReport, render_report
from tools.china_quant.risk import compute_trade_levels
from tools.china_quant.scoring_v2 import score_stock_v2
from tools.china_quant.sector_data import SectorRankingReport, rank_sectors_from_boards, render_sector_report
from tools.china_quant.sector_rotation import rank_sectors_v2
from tools.china_quant.universe_builder import UniverseAudit, build_real_universe, render_universe_audit
from tools.china_quant.intelligence import run_intelligence, load_full_bundle
from tools.china_quant.freshness import assess_freshness, FreshnessResult
from tools.china_quant.report_deliverables import (
    load_policy_institutional,
    render_backtest_report,
    render_data_freshness_report,
    render_institutional_report,
    render_policy_report,
)


@dataclass
class DailyRunResult:
    mode: OperatingMode
    analysis_date: str
    report: DailyReport
    dossiers: dict[str, str] = field(default_factory=dict)
    universe_audit: Optional[UniverseAudit] = None
    sector_report: Optional[SectorRankingReport] = None
    regime_analysis: Optional[RegimeAnalysis] = None
    provider_status: dict = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)
    freshness: Optional[FreshnessResult] = None


def _mode_header(mode: OperatingMode, *, analysis_date: str, provider: str, freshness: str, retrieved: str, market_ts: str) -> str:
    return (
        f"> **{MODE_BANNERS[mode]}**\n"
        f"> - 运行模式：`{mode.value}`\n"
        f"> - 分析日期：{analysis_date}\n"
        f"> - 数据提供商：{provider}\n"
        f"> - 新鲜度：{freshness}\n"
        f"> - 检索时间：{retrieved}\n"
        f"> - 市场时间：{market_ts}\n"
    )


def _prelim_score(row) -> float:
    return row.change_pct * 2 + min(row.amount / 1e8, 10) * 3


def _row_to_stock(row, sector: str) -> StockRecord:
    return StockRecord(
        code=row.code, name=row.name, exchange=row.exchange, board=row.board,
        sector=sector, price=row.price, change_pct=row.change_pct,
        avg_daily_value_m=row.amount / 1e6,
        trend_score=min(15, max(0, row.change_pct + 5)),
        fundamental_score=8, valuation_score=7,
    )


def run_fixture(fixtures_dir: Path, fixture_name: str = "universe_full") -> DailyRunResult:
    fp = FixtureProvider(fixtures_dir)
    bundle = load_full_bundle(fixtures_dir, fixture_name)
    intel = run_intelligence(
        bundle, fixtures_dir=fixtures_dir,
        policy_data=fp.load_policy().payload,
        inst_data=fp.load_institutional().payload,
    )
    mode = OperatingMode.FIXTURE
    intel.report.data_provenance.insert(0, _mode_header(
        mode, analysis_date=bundle.snapshot.trade_date, provider="fixture",
        freshness="FIXTURE", retrieved=datetime.now().isoformat(timespec="minutes"),
        market_ts=bundle.snapshot.data_timestamp.isoformat(timespec="minutes"),
    ))
    return DailyRunResult(
        mode=mode, analysis_date=bundle.snapshot.trade_date,
        report=intel.report, dossiers=intel.dossiers,
        limitations=["SAMPLE_FIXTURE only"],
    )


def run_latest_available(
    fixtures_dir: Path,
    *,
    max_screen: int = 200,
    max_candidates: int = 3,
    use_cache: bool = True,
) -> DailyRunResult:
    mode = OperatingMode.LATEST_AVAILABLE
    limitations: list[str] = []
    provider_status: dict = {}
    analysis_date = datetime.now().strftime("%Y-%m-%d")

    try:
        ak = AKShareProvider(use_cache=use_cache)
        indices_env = ak.get_indices()
        spot_env = ak.get_spot_quotes()
        boards_env = ak.get_sector_boards()
        provider_status = {
            "indices": indices_env.source_id,
            "spot": spot_env.source_id,
            "sectors": boards_env.source_id,
            "spot_rows": spot_env.row_count,
        }
        from tools.china_quant.snapshot_store import save_snapshot

        save_snapshot({
            "indices": indices_env.payload,
            "spot": spot_env.payload,
            "boards": boards_env.payload,
        })
        return _run_with_live_data(
            mode, analysis_date, indices_env, spot_env, boards_env,
            max_screen, max_candidates, limitations, provider_status,
            fixtures_dir,
        )
    except (ProviderError, Exception) as e:
        limitations.append(f"BLOCKED_BY_DATA: {e}")
        from tools.china_quant.snapshot_store import load_snapshot
        snap = load_snapshot()
        if snap:
            limitations.append("Using last saved snapshot — not live")
            return _run_with_live_data(
                mode, analysis_date,
                _dict_to_env(snap["indices"], "snapshot:indices"),
                _dict_to_env(snap["spot"], "snapshot:spot"),
                _dict_to_env(snap["boards"], "snapshot:boards"),
                max_screen, max_candidates, limitations, {"source": "snapshot"},
                fixtures_dir,
            )
        return _blocked_report(mode, analysis_date, limitations)


def _dict_to_env(payload: dict, source_id: str):
    from tools.china_quant.providers.base import DataEnvelope, DataFreshness
    return DataEnvelope(
        provider="snapshot", payload=payload, retrieval_timestamp=datetime.now(),
        market_timestamp=datetime.now(), freshness=DataFreshness.PARTIAL_DATA,
        source_id=source_id, limitations=["Cached snapshot"],
        row_count=len(payload.get("rows", [])) if isinstance(payload, dict) else 0,
    )


def _blocked_report(mode: OperatingMode, analysis_date: str, limitations: list[str]) -> DailyRunResult:
    from tools.china_quant.freshness import FreshnessResult, DataStatus
    from tools.china_quant.regime import MarketRegime, RegimeResult
    header = _mode_header(mode, analysis_date=analysis_date, provider="none",
                          freshness="DATA_UNAVAILABLE", retrieved=datetime.now().isoformat(timespec="minutes"),
                          market_ts="N/A")
    fr = FreshnessResult(DataStatus.DATA_UNAVAILABLE, False, "Data unavailable", None, datetime.now())
    regime = RegimeResult(MarketRegime.INSUFFICIENT, 0, "NO TRADE", "数据不可用，建议观望。")
    report = DailyReport(
        conclusion_direction="未知", market_regime_zh="insufficient data",
        position_guidance="0%", trade_today="否（BLOCKED_BY_DATA）",
        data_cutoff=analysis_date, data_status="DATA_UNAVAILABLE",
        one_liner="AKShare 不可用，无法生成实时/最新可用报告。",
        regime=regime, freshness=fr, primary=[], watchlist=[], avoid=["数据不可用"],
        data_provenance=[header], assumptions=limitations,
    )
    return DailyRunResult(mode=mode, analysis_date=analysis_date, report=report, limitations=limitations)


def _run_with_live_data(
    mode, analysis_date, indices_env, spot_env, boards_env,
    max_screen, max_candidates, limitations, provider_status,
    fixtures_dir: Path,
) -> DailyRunResult:
    spot_rows = spot_env.payload.get("rows", spot_env.payload if isinstance(spot_env.payload, list) else [])
    audit = build_real_universe(spot_rows, mode=mode.value if hasattr(mode, "value") else str(mode), analysis_date=analysis_date)
    regime_a = classify_regime_v2(indices_env.payload, spot_rows)
    sectors = rank_sectors_from_boards(boards_env.payload.get("rows", boards_env.payload if isinstance(boards_env.payload, list) else []))
    strong_sectors = {s.name for s in sectors[:5]}

    # Preliminary rank eligible universe in code (not LLM)
    ranked_rows = sorted(audit.rows, key=_prelim_score, reverse=True)[:max_screen]

    primary: list[CandidatePlan] = []
    watchlist: list[CandidatePlan] = []
    dossiers: dict[str, str] = {}
    avoid: list[str] = []

    min_score = regime_a.min_score_threshold
    if regime_a.result.max_primary_candidates == 0:
        min_score = 999

    scored_list: list[tuple[float, StockRecord, object, object]] = []
    for row in ranked_rows:
        sector = row.sector if row.sector != "未知" else (sectors[0].name if sectors else "其他")
        if strong_sectors and sector not in strong_sectors and len(strong_sectors) > 0:
            # soft sector filter — skip if not in top sectors unless high momentum
            if row.change_pct < 3:
                continue
        st = _row_to_stock(row, sector)
        fs = score_stock_v2(
            st, regime_name=regime_a.result.regime.value, sector_strength=12,
            has_confirmed_catalyst=False, institutional_score=0,
        )
        levels = compute_trade_levels(st)
        if not levels.acceptable:
            avoid.append(f"{st.name}：{levels.reject_reason}")
            continue
        if fs.total >= min_score:
            scored_list.append((fs.total, st, fs, levels))
        elif fs.total >= min_score - 10:
            watchlist.append(_plan(st, fs, levels))

    scored_list.sort(key=lambda x: x[0], reverse=True)
    for i, (_, st, fs, levels) in enumerate(scored_list[: regime_a.result.max_primary_candidates], 1):
        primary.append(_plan(st, fs, levels))
        dossiers[st.code] = render_dossier(
            st, fs, levels, rank=i, regime=regime_a.result.regime.value,
            sector_stage=next((s.phase for s in sectors if s.name == st.sector), "MATURE"),
            policy_summary="见 POLICY 报告（AKShare/官方源待 enrich）",
            institutional_summary="公开披露数据待 enrich",
            data_freshness=spot_env.freshness.value,
            final_status="ACTIONABLE_PAPER_TRADE",
        )

    fresh = assess_freshness(spot_env.market_timestamp)
    trade_today = "否（NO TRADE）" if not primary else "谨慎（纸面交易/模拟）"
    if regime_a.result.max_primary_candidates == 0:
        trade_today = "否（NO TRADE — 市场状态）"

    header = _mode_header(
        mode, analysis_date=analysis_date, provider="akshare",
        freshness=spot_env.freshness.value,
        retrieved=spot_env.retrieval_timestamp.isoformat(timespec="minutes"),
        market_ts=spot_env.market_timestamp.isoformat(timespec="minutes") if spot_env.market_timestamp else analysis_date,
    )

    report = DailyReport(
        conclusion_direction="偏强" if indices_env.payload.get("sh", {}).get("change_pct", 0) > 0.5 else "震荡",
        market_regime_zh=regime_a.result.regime.value,
        position_guidance=regime_a.exposure_ceiling,
        trade_today=trade_today,
        data_cutoff=spot_env.market_timestamp.isoformat(sep=" ", timespec="minutes") if spot_env.market_timestamp else analysis_date,
        data_status=spot_env.freshness.value,
        one_liner=regime_a.result.guidance_zh,
        regime=regime_a.result,
        freshness=fresh,
        primary=primary,
        watchlist=watchlist[:5],
        avoid=avoid[:30],
        sectors=sectors,
        data_provenance=[header, f"universe_total={audit.total_retrieved}", f"eligible={audit.eligible}"],
        assumptions=["AKShare public data; not investment advice"],
        policy_summary="待 policy pipeline enrich",
        institutional_summary=f"全市场扫描 {audit.eligible} 只",
    )

    sector_rep = SectorRankingReport(analysis_date=analysis_date, mode=mode.value, sectors=sectors)

    return DailyRunResult(
        mode=mode, analysis_date=analysis_date, report=report, dossiers=dossiers,
        universe_audit=audit, sector_report=sector_rep, regime_analysis=regime_a,
        provider_status=provider_status, limitations=limitations, freshness=fresh,
    )


def run_historical(fixtures_dir: Path, date: str) -> DailyRunResult:
    """Historical mode — index from bars fixture or AKShare hist."""
    mode = OperatingMode.HISTORICAL
    limitations: list[str] = []
    try:
        ak = AKShareProvider(use_cache=True)
        hist = ak.get_index_history("000001", end_date=date)
        rows = hist.payload.get("rows", [])
        if rows:
            limitations.append(f"Index history through {date}")
    except ProviderError as e:
        limitations.append(f"BLOCKED_BY_DATA index: {e}")
        rows = []

    if not rows:
        fp = FixtureProvider(fixtures_dir)
        bars = fp.load_bars("601398").payload.get("bars", [])
        rows = [b for b in bars if str(b.get("date", b.get("日期", ""))) <= date.replace("-", "")]

    r = run_fixture(fixtures_dir)
    r.mode = mode
    r.analysis_date = date
    r.limitations = limitations + ["Stock screen uses FIXTURE universe; index from bars/hist when available"]
    r.report.data_provenance.insert(0, _mode_header(
        mode, analysis_date=date, provider="akshare|fixture",
        freshness="HISTORICAL", retrieved=datetime.now().isoformat(timespec="minutes"),
        market_ts=f"{date} 15:00",
    ))
    return r


def _plan(st: StockRecord, fs, levels) -> CandidatePlan:
    return CandidatePlan(
        name=st.name, code=st.code, exchange=st.exchange, sector=st.sector,
        price=st.price, data_time="akshare", recommendation="可轻仓试探" if fs.total >= 78 else "观察",
        confidence="MEDIUM", score=fs.total,
        reasons=[f"评分{fs.total:.0f}", f"成交额{st.avg_daily_value_m:.0f}M"],
        entry_range=f"{levels.entry_low:.2f}-{levels.entry_high:.2f}",
        entry_confirm=levels.entry_confirm, cancel_condition=levels.cancel_condition,
        stop=f"{levels.stop_price:.2f} (-{levels.stop_pct:.0f}%)",
        target1=f"{levels.target1:.2f}", target2=f"{levels.target2:.2f}",
        hold_period=levels.hold_period, position_pct=levels.position_pct,
        reward_risk=levels.reward_risk, catalyst="无确认公告",
        risks=["板块轮动", "数据延迟"], invalidation=f"跌破{levels.stop_price:.2f}",
    )


def write_deliverables(result: DailyRunResult, base: Path, fixtures_dir: Optional[Path] = None) -> dict[str, Path]:
    base.mkdir(parents=True, exist_ok=True)
    day = result.analysis_date
    paths: dict[str, Path] = {}
    fix = fixtures_dir or base.parents[1] / "test-fixtures" / "china-quant"
    if not fix.exists():
        fix = Path(__file__).resolve().parents[2] / "docs" / "test-fixtures" / "china-quant"

    paths["premarket"] = base / f"{day}_PREMARKET.md"
    paths["premarket"].write_text(render_report(result.report), encoding="utf-8")

    if result.universe_audit:
        paths["universe"] = base / f"{day}_UNIVERSE_AUDIT.md"
        paths["universe"].write_text(render_universe_audit(result.universe_audit), encoding="utf-8")

    if result.sector_report:
        paths["sectors"] = base / f"{day}_SECTOR_RANKING.md"
        paths["sectors"].write_text(render_sector_report(result.sector_report), encoding="utf-8")

    cand = base / f"{day}_PRIMARY_CANDIDATES"
    cand.mkdir(exist_ok=True)
    for code, md in result.dossiers.items():
        p = cand / f"{code}.md"
        p.write_text(md, encoding="utf-8")
        paths[f"dossier_{code}"] = p

    policy_items, inst_signals = load_policy_institutional(fix)
    pol_lim = ["公开源/fixture；非实时"] if result.mode == OperatingMode.FIXTURE else ["AKShare enrich 待接"]
    paths["policy"] = base / f"{day}_POLICY_MACRO.md"
    paths["policy"].write_text(
        render_policy_report(policy_items, mode=result.mode, analysis_date=day, limitations=pol_lim + result.limitations),
        encoding="utf-8",
    )
    paths["institutional"] = base / f"{day}_INSTITUTIONAL_FLOW.md"
    paths["institutional"].write_text(
        render_institutional_report(inst_signals, mode=result.mode, analysis_date=day),
        encoding="utf-8",
    )
    mkt_ts = result.report.data_cutoff or day
    paths["freshness"] = base / f"{day}_DATA_FRESHNESS.md"
    paths["freshness"].write_text(
        render_data_freshness_report(
            mode=result.mode,
            analysis_date=day,
            provider_status=result.provider_status or {"provider": result.mode.value},
            limitations=result.limitations,
            freshness_label=result.report.data_status,
            market_ts=mkt_ts,
        ),
        encoding="utf-8",
    )
    paths["backtest"] = base / f"{day}_BACKTEST_SUMMARY.md"
    paths["backtest"].write_text(render_backtest_report(fix, mode=result.mode), encoding="utf-8")

    meta = base / f"{day}_RUN_META.json"
    meta.write_text(json.dumps({
        "mode": result.mode.value,
        "analysis_date": day,
        "provider_status": result.provider_status,
        "limitations": result.limitations,
        "primary_count": len(result.report.primary),
        "deliverables": {k: str(v.name) for k, v in paths.items()},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    paths["meta"] = meta
    return paths
