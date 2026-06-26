"""Paper autopilot — real-time quote monitoring and rule-based paper execution."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from gateway.config import ROOT
from gateway.risk.engine import OrderIntent

MONITOR_STATE = ROOT / "data" / "gateway" / "paper_monitor.json"
SIGNAL_LOG = ROOT / "data" / "gateway" / "paper_monitor_signals.jsonl"

BUY_ZONE_BUFFER = 0.018
SELL_EARLY_FACTOR = 0.996
STOP_TIGHTEN_FACTOR = 1.008
SIGNAL_COOLDOWN_SEC = 300


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_monitor_state() -> dict[str, Any]:
    if not MONITOR_STATE.exists():
        return {"enabled": False, "candidates": [], "last_tick": None, "last_error": None}
    try:
        return json.loads(MONITOR_STATE.read_text(encoding="utf-8"))
    except Exception:
        return {"enabled": False, "candidates": [], "last_tick": None, "last_error": None}


def save_monitor_state(state: dict[str, Any]) -> None:
    MONITOR_STATE.parent.mkdir(parents=True, exist_ok=True)
    MONITOR_STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def set_monitor_portfolio(candidates: list[dict[str, Any]], *, enabled: bool = True) -> dict[str, Any]:
    """Persist screener candidates with trade zones for live monitoring."""
    rows = []
    for c in candidates:
        sym = c.get("symbol")
        if not sym:
            continue
        rows.append({
            "symbol": sym,
            "name": c.get("name") or sym,
            "score": float(c.get("final_score") or c.get("score") or 0),
            "suggested_qty": int(c.get("suggested_qty") or c.get("quantity") or 100),
            "trade_zones": c.get("trade_zones") or {},
            "invalidation_conditions": c.get("invalidation_conditions") or [],
            "reasons_not_to_trade": c.get("reasons_not_to_trade") or [],
            "valid_for_purchase": bool(c.get("valid_for_purchase", True)),
        })
    state = {
        "enabled": enabled and bool(rows),
        "candidates": rows,
        "updated_at": _now(),
        "last_tick": None,
        "last_error": None,
    }
    save_monitor_state(state)
    return state


def _fetch_real_prices(*, refresh: bool = True) -> tuple[dict[str, float], dict[str, Any]]:
    from quant.application.live_market_service import ensure_live_quotes, live_price_map

    snap = ensure_live_quotes(refresh=refresh, max_age_sec=90)
    prices = live_price_map()
    meta = {
        "quote_count": len(prices),
        "provider": snap.get("provider"),
        "retrieved_at": snap.get("retrieved_at"),
        "is_live": snap.get("is_live"),
        "blocked": not prices,
        "stale_fallback": bool(snap.get("stale_fallback")),
    }
    return prices, meta


def _emit_signal(event: dict[str, Any]) -> None:
    SIGNAL_LOG.parent.mkdir(parents=True, exist_ok=True)
    with SIGNAL_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def _cooldown_active(state: dict[str, Any], sym: str, side: str) -> bool:
    last_actions = state.get("last_actions") or {}
    key = f"{sym}:{side}"
    ts = last_actions.get(key)
    if not ts:
        return False
    try:
        from datetime import datetime, timezone

        then = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - then).total_seconds() < SIGNAL_COOLDOWN_SEC
    except Exception:
        return False


def _mark_action(state: dict[str, Any], sym: str, side: str) -> None:
    last_actions = state.setdefault("last_actions", {})
    last_actions[f"{sym}:{side}"] = _now()


def _recent_signals(limit: int = 30) -> list[dict[str, Any]]:
    if not SIGNAL_LOG.exists():
        return []
    lines = SIGNAL_LOG.read_text(encoding="utf-8").splitlines()
    out = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return out


def run_monitor_tick(paper: Any, *, user_id: str = "default", refresh_quotes: bool = True) -> dict[str, Any]:
    """One monitoring cycle — uses REAL live prices only; no synthetic fills."""
    from gateway.brokers.operations_ledger import append_operation

    state = load_monitor_state()
    if not state.get("enabled"):
        return {"ok": False, "blocked": True, "reason": "MONITOR_NOT_ENABLED"}

    prices, quote_meta = _fetch_real_prices(refresh=refresh_quotes)
    if not prices or quote_meta.get("blocked"):
        err = "实时行情不可用 — 无法基于真实价格监控/下单，请先刷新行情"
        state["last_error"] = err
        state["last_tick"] = _now()
        save_monitor_state(state)
        return {"ok": False, "blocked": True, "reason": err, "quote_meta": quote_meta}

    actions: list[dict[str, Any]] = []
    positions = {sym: pos for sym, pos in getattr(paper, "positions", {}).items()}
    candidates = state.get("candidates") or []

    # --- SELL rules for held positions ---
    for sym, pos in list(positions.items()):
        px = prices.get(sym)
        if px is None:
            actions.append({"symbol": sym, "action": "SKIP", "reason": "NO_LIVE_PRICE"})
            continue
        cand = next((c for c in candidates if c["symbol"] == sym), None)
        zones = (cand or {}).get("trade_zones") or {}
        qty = int(getattr(pos, "available_qty", 0) or getattr(pos, "quantity", 0))
        if qty <= 0:
            continue
        if _cooldown_active(state, sym, "SELL"):
            actions.append({"symbol": sym, "action": "SKIP", "reason": "SELL_COOLDOWN"})
            continue
        stop = float(zones.get("stop_loss") or 0)
        take = float(zones.get("sell_zone_low") or 0)
        take_high = float(zones.get("sell_zone_high") or 0)
        sell_reason = None
        if stop > 0 and px <= stop * STOP_TIGHTEN_FACTOR:
            sell_reason = f"STOP_LOSS live={px:.2f} <= {stop * STOP_TIGHTEN_FACTOR:.2f}"
        elif take > 0 and px >= take * SELL_EARLY_FACTOR:
            sell_reason = f"TAKE_PROFIT live={px:.2f} >= {take * SELL_EARLY_FACTOR:.2f}"
        elif take_high > 0 and px >= take_high * 0.998:
            sell_reason = f"TARGET_HIGH live={px:.2f} >= {take_high * 0.998:.2f}"
        if sell_reason:
            intent = OrderIntent(
                client_order_id=str(uuid4()),
                run_id=str(uuid4())[:8],
                strategy_id="paper_autopilot",
                model_id="live_monitor",
                symbol=sym,
                side="SELL",
                quantity=qty,
                limit_price=px,
                notional_cny=px * qty,
            )
            order = paper.submit(intent, data_fresh=True, market_price=px)
            act = {
                "symbol": sym,
                "side": "SELL",
                "quantity": qty,
                "live_price": px,
                "reason": sell_reason,
                "state": order.state.value,
                "ok": order.state.value == "FILLED",
            }
            actions.append(act)
            _mark_action(state, sym, "SELL")
            _emit_signal({**act, "ts": _now(), "quote_meta": quote_meta})
            append_operation(
                mode="paper",
                action="autopilot_sell",
                user_id=user_id,
                symbol=sym,
                session="intraday",
                details={"live_price": px, "reason": sell_reason},
                status="ok" if act["ok"] else "rejected",
            )

    # --- BUY rules for watchlist candidates ---
    for cand in candidates:
        sym = cand["symbol"]
        if sym in positions:
            continue
        if not cand.get("valid_for_purchase", True):
            continue
        if cand.get("reasons_not_to_trade"):
            continue
        px = prices.get(sym)
        if px is None:
            actions.append({"symbol": sym, "action": "SKIP", "reason": "NO_LIVE_PRICE"})
            continue
        zones = cand.get("trade_zones") or {}
        lo = float(zones.get("buy_zone_low") or 0)
        hi = float(zones.get("buy_zone_high") or 0)
        if lo <= 0 or hi <= 0:
            actions.append({"symbol": sym, "action": "SKIP", "reason": "NO_BUY_ZONE"})
            continue
        if zones.get("chase_warning") and px >= hi * 0.998:
            actions.append({"symbol": sym, "action": "SKIP", "reason": "LIMIT_UP_CHASE"})
            continue
        lo_adj = lo * (1.0 - BUY_ZONE_BUFFER * 0.5)
        hi_adj = hi * (1.0 + BUY_ZONE_BUFFER)
        score = float(cand.get("score") or 0)
        momentum_ok = score >= 65 and lo * 0.99 <= px <= hi * (1.0 + BUY_ZONE_BUFFER * 1.5)
        in_zone = lo_adj <= px <= hi_adj or momentum_ok
        if not in_zone:
            actions.append({
                "symbol": sym,
                "action": "WATCH",
                "live_price": px,
                "buy_zone": [lo, hi],
                "reason": f"价格 ¥{px:.2f} 不在买入区间 ¥{lo:.2f}–¥{hi:.2f}",
            })
            continue
        if _cooldown_active(state, sym, "BUY"):
            actions.append({"symbol": sym, "action": "SKIP", "reason": "BUY_COOLDOWN"})
            continue
        qty = int(cand.get("suggested_qty") or 100)
        if qty < 100:
            qty = 100
        qty = (qty // 100) * 100
        intent = OrderIntent(
            client_order_id=str(uuid4()),
            run_id=str(uuid4())[:8],
            strategy_id="paper_autopilot",
            model_id="live_monitor",
            symbol=sym,
            side="BUY",
            quantity=qty,
            limit_price=px,
            notional_cny=px * qty,
        )
        order = paper.submit(intent, data_fresh=True, market_price=px)
        act = {
            "symbol": sym,
            "side": "BUY",
            "quantity": qty,
            "live_price": px,
            "reason": f"BUY_ZONE live={px:.2f} in [{lo_adj:.2f},{hi_adj:.2f}]"
            + (" momentum" if momentum_ok and not (lo <= px <= hi) else ""),
            "state": order.state.value,
            "ok": order.state.value == "FILLED",
        }
        actions.append(act)
        _mark_action(state, sym, "BUY")
        _emit_signal({**act, "ts": _now(), "quote_meta": quote_meta})
        append_operation(
            mode="paper",
            action="autopilot_buy",
            user_id=user_id,
            symbol=sym,
            session="intraday",
            details={"live_price": px, "buy_zone": [lo, hi]},
            status="ok" if act["ok"] else "rejected",
        )

    # Mark-to-market with live prices
    if hasattr(paper, "mark_to_market"):
        paper.mark_to_market(prefer_live=True)

    live_lines = []
    for cand in candidates:
        sym = cand["symbol"]
        px = prices.get(sym)
        if px is None:
            continue
        pos = positions.get(sym)
        live_lines.append({
            "symbol": sym,
            "name": cand.get("name"),
            "live_price": px,
            "held": sym in positions,
            "quantity": int(getattr(pos, "quantity", 0)) if pos else 0,
            "trade_zones": cand.get("trade_zones"),
        })

    state["last_tick"] = _now()
    state["last_error"] = None
    state["last_quote_meta"] = quote_meta
    save_monitor_state(state)

    return {
        "ok": True,
        "quote_meta": quote_meta,
        "actions": actions,
        "watchlist_live": live_lines,
        "signals_recent": _recent_signals(20),
        "account": paper.account_summary() if hasattr(paper, "account_summary") else paper.pnl_summary(),
    }


def monitor_status(paper: Any) -> dict[str, Any]:
    state = load_monitor_state()
    prices, quote_meta = _fetch_real_prices(refresh=False)
    positions = {sym: pos for sym, pos in getattr(paper, "positions", {}).items()}
    watchlist_live = []
    for cand in state.get("candidates") or []:
        sym = cand["symbol"]
        px = prices.get(sym)
        pos = positions.get(sym)
        watchlist_live.append({
            "symbol": sym,
            "name": cand.get("name"),
            "live_price": px,
            "held": sym in positions,
            "quantity": int(getattr(pos, "quantity", 0)) if pos else 0,
            "trade_zones": cand.get("trade_zones"),
        })
    return {
        **state,
        "quote_meta": quote_meta,
        "watchlist_live": watchlist_live,
        "signals_recent": _recent_signals(15),
        "account": paper.account_summary() if hasattr(paper, "account_summary") else {},
    }
