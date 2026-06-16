"""Build real A-share universe from AKShare spot + master."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

MIN_AMOUNT = 30_000_000  # 3000万成交额
MIN_HISTORY_DAYS = 60


@dataclass
class UniverseRow:
    code: str
    name: str
    exchange: str
    board: str
    price: float
    change_pct: float
    amount: float
    volume: float
    is_st: bool
    sector: str = "未知"
    listing_date: str = ""
    market_cap: float = 0.0
    history_days: int = 0


@dataclass
class UniverseAudit:
    mode: str
    analysis_date: str
    total_retrieved: int = 0
    eligible: int = 0
    excluded: int = 0
    exclusion_counts: dict[str, int] = field(default_factory=dict)
    excluded_samples: list[tuple[str, str, str]] = field(default_factory=list)
    provider_failures: list[str] = field(default_factory=list)
    missing_data_rate: float = 0.0
    rows: list[UniverseRow] = field(default_factory=list)


def _exclude_reason(row: dict[str, Any]) -> str | None:
    if row.get("is_st"):
        return "ST默认排除"
    if row.get("price", 0) <= 0:
        return "无效价格"
    if row.get("amount", 0) < MIN_AMOUNT:
        return "流动性不足"
    if row.get("suspended"):
        return "停牌"
    if row.get("at_limit_up"):
        return "涨停无法买入"
    if row.get("history_days", 999) < MIN_HISTORY_DAYS:
        return "历史不足"
    return None


def build_real_universe(spot_rows: list[dict], *, mode: str, analysis_date: str) -> UniverseAudit:
    audit = UniverseAudit(mode=mode, analysis_date=analysis_date, total_retrieved=len(spot_rows))
    eligible: list[UniverseRow] = []

    for r in spot_rows:
        reason = _exclude_reason(r)
        if reason:
            audit.excluded += 1
            audit.exclusion_counts[reason] = audit.exclusion_counts.get(reason, 0) + 1
            if len(audit.excluded_samples) < 20:
                audit.excluded_samples.append((r["code"], r["name"], reason))
            continue
        eligible.append(
            UniverseRow(
                code=r["code"], name=r["name"], exchange=r.get("exchange", "SH"),
                board=r.get("board", "MAIN_SH"), price=r["price"], change_pct=r["change_pct"],
                amount=r["amount"], volume=r["volume"], is_st=r.get("is_st", False),
                sector=r.get("sector", "未知"), history_days=r.get("history_days", 120),
            )
        )

    audit.eligible = len(eligible)
    audit.rows = eligible
    audit.missing_data_rate = sum(1 for r in spot_rows if r.get("price", 0) <= 0) / max(len(spot_rows), 1)
    return audit


def render_universe_audit(audit: UniverseAudit) -> str:
    lines = [
        f"# Universe Audit — {audit.analysis_date}",
        "",
        f"- **Mode**: {audit.mode}",
        f"- Total retrieved: {audit.total_retrieved}",
        f"- Eligible: {audit.eligible}",
        f"- Excluded: {audit.excluded}",
        f"- Missing price rate: {audit.missing_data_rate:.2%}",
        "",
        "## Exclusion counts",
        "",
    ]
    for k, v in sorted(audit.exclusion_counts.items(), key=lambda x: -x[1]):
        lines.append(f"- {k}: {v}")
    if audit.excluded_samples:
        lines += ["", "## Sample exclusions", ""]
        for code, name, reason in audit.excluded_samples[:10]:
            lines.append(f"- {code} {name}: {reason}")
    return "\n".join(lines)
