"""Mac-simple broker assist — login once in browser, then auto-open + pre-fill orders.

No VM, no Sidecar. User logs in manually once; we reuse the session to open
the official Eastmoney trade page with stock/qty/price filled when possible.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gateway.brokers.broker_launcher import build_broker_urls, launch_cn_broker, symbol_to_market
from gateway.config import ROOT

SESSION_DIR = ROOT / "data" / "gateway" / "browser_sessions"
ASSIST_LOG = ROOT / "data" / "gateway" / "broker_assist.jsonl"

BROKER_LOGIN_URLS = {
    "eastmoney_manual": "https://jywg.eastmoneysec.com/",
    "huatai_zhangle": "https://service.htsc.com.cn/service/login.jsp",
    "flush_tonghuashun": "https://eq.10jqka.com.cn/",
    "gtja_junhong": "https://dl.app.gtja.com/public/m/index.html",
    "cms_zhaoshang": "https://www.newone.com.cn/main/onlinebusiness/tradingsoftware/index.html",
    "citic_xintou": "https://www.citics.com/newsite/online/index.html",
    "gf_yitajin": "https://store.gf.com.cn/",
    "galaxy_chinastock": "https://www.chinastock.com.cn/",
    "pingan_securities": "https://stock.pingan.com/",
}

BROKER_LOGIN_HINTS: dict[str, list[str]] = {
    "eastmoney_manual": ["text=银证转账", "text=当日委托", "jywg"],
    "huatai_zhangle": ["text=涨乐", "text=客户号", "htsc", "service.htsc"],
    "flush_tonghuashun": ["text=交易", "text=登录", "10jqka", "eq.10jqka"],
    "gtja_junhong": ["text=君弘", "text=交易", "gtja"],
    "cms_zhaoshang": ["text=招商", "text=一户通", "newone"],
    "citic_xintou": ["text=中信", "text=信e投", "citics"],
    "gf_yitajin": ["text=广发", "text=易淘金", "gf.com"],
    "galaxy_chinastock": ["text=银河", "text=交易", "chinastock"],
    "pingan_securities": ["text=平安", "text=证券", "pingan"],
}


def _ensure_playwright():
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        return True
    except ImportError:
        return False


def session_path(broker_id: str) -> Path:
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    return SESSION_DIR / f"{broker_id}.json"


def has_saved_session(broker_id: str) -> bool:
    p = session_path(broker_id)
    return p.exists() and p.stat().st_size > 100


def session_status(broker_id: str) -> dict[str, Any]:
    p = session_path(broker_id)
    return {
        "broker_id": broker_id,
        "saved": has_saved_session(broker_id),
        "path": str(p),
        "updated_at": datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat() if p.exists() else "",
        "playwright_ready": _ensure_playwright(),
    }


def run_login_assist(broker_id: str = "eastmoney_manual", *, wait_seconds: int = 180) -> dict[str, Any]:
    """Open official login page; user logs in; save cookies for reuse."""
    if not _ensure_playwright():
        subprocess.run([sys.executable, "-m", "pip", "install", "playwright", "-q"], check=False)
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=False)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        url = BROKER_LOGIN_URLS.get(broker_id, "https://jywg.eastmoneysec.com/")
        launch_cn_broker(broker_id, target="trade_login")
        return {
            "ok": True,
            "mode": "manual_browser_only",
            "message": f"已打开登录页，请登录后重试（需 pip install playwright）",
            "url": url,
        }

    login_url = BROKER_LOGIN_URLS.get(broker_id) or build_broker_urls(broker_id).get("trade_login", "")
    out_path = session_path(broker_id)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(login_url, wait_until="domcontentloaded", timeout=60000)
        page.bring_to_front()
        logged_in = False
        deadline = min(wait_seconds, 300)
        for _ in range(deadline // 2):
            try:
                if _page_looks_logged_in(page, broker_id):
                    logged_in = True
                    break
            except Exception:
                pass
            page.wait_for_timeout(2000)
        context.storage_state(path=str(out_path))
        browser.close()
    return {
        "ok": True,
        "mode": "session_saved",
        "logged_in_detected": logged_in,
        "message": (
            f"登录会话已保存（{'已检测到登录态' if logged_in else '请确认已在浏览器完成登录'}）"
        ),
        "broker_id": broker_id,
        "path": str(out_path),
        "url": login_url,
    }


def _page_looks_logged_in(page: Any, broker_id: str) -> bool:
    """Heuristic: logged-in broker pages show account/trade UI."""
    hints = [
        "text=买入",
        "text=卖出",
        "text=持仓",
        "text=资金",
        "text=委托",
        "#buyPanel",
        ".trade-panel",
    ]
    if broker_id == "eastmoney_manual":
        hints.extend(BROKER_LOGIN_HINTS.get("eastmoney_manual", []))
    else:
        hints.extend(BROKER_LOGIN_HINTS.get(broker_id, []))
    for sel in hints:
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible(timeout=500):
                return True
        except Exception:
            continue
    url = page.url or ""
    return any(k in url for k in ("trade", "jywg", "order", "buy"))


def auto_import_watchlist_csv(broker_id: str, user_id: str = "default") -> dict[str, Any]:
    """Upload latest watchlist CSV to broker import page if file input exists."""
    from gateway.screener.watchlist import list_watchlist

    export_dir = ROOT / "data" / "gateway" / "watchlist_exports"
    csv_files = sorted(export_dir.glob(f"{broker_id}_*_watchlist.csv"), reverse=True)
    if not csv_files:
        items = list_watchlist(user_id)
        if not items:
            return {"ok": False, "attempted": False, "message": "无 CSV 可导入"}
        assist_sync_watchlist(broker_id, items, max_symbols=len(items))
        csv_files = sorted(export_dir.glob(f"{broker_id}_*_watchlist.csv"), reverse=True)
    if not csv_files or not has_saved_session(broker_id) or not _ensure_playwright():
        return {"ok": False, "attempted": False, "message": "需先登录券商"}

    csv_path = csv_files[0]
    imported = False
    try:
        from playwright.sync_api import sync_playwright
        urls = build_broker_urls(broker_id)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(storage_state=str(session_path(broker_id)))
            page = context.new_page()
            for target in (urls.get("trade_login"), urls.get("portal")):
                if not target:
                    continue
                page.goto(target, wait_until="domcontentloaded", timeout=60000)
                for sel in ["input[type='file']", "input[accept*='csv']"]:
                    loc = page.locator(sel).first
                    if loc.count():
                        loc.set_input_files(str(csv_path))
                        page.wait_for_timeout(2000)
                        imported = True
                        break
                if imported:
                    break
            browser.close()
    except Exception as exc:
        return {"ok": False, "attempted": True, "message": str(exc), "csv_file": str(csv_path)}

    return {
        "ok": imported,
        "attempted": True,
        "imported": imported,
        "csv_file": str(csv_path),
        "message": "已上传自选 CSV 到券商页面" if imported else "未找到导入入口，已通过行情页加自选",
    }


def auto_export_fills(broker_id: str) -> dict[str, Any]:
    """Navigate broker trade history and import fills into gateway ledger."""
    if not has_saved_session(broker_id) or not _ensure_playwright():
        return {"ok": False, "attempted": False, "message": "需先登录券商"}

    scraped: list[dict[str, Any]] = []
    try:
        from playwright.sync_api import sync_playwright
        urls = build_broker_urls(broker_id)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(storage_state=str(session_path(broker_id)))
            page = context.new_page()
            page.goto(urls.get("trade_login", ""), wait_until="domcontentloaded", timeout=60000)
            for sel in ["text=当日成交", "text=成交查询", "text=历史成交", "text=查询"]:
                try:
                    loc = page.locator(sel).first
                    if loc.count() and loc.is_visible(timeout=1500):
                        loc.click(timeout=3000)
                        page.wait_for_timeout(2000)
                        break
                except Exception:
                    continue
            rows = page.locator("table tr").all()
            for row in rows[:30]:
                try:
                    cells = [c.inner_text().strip() for c in row.locator("td").all()]
                    if len(cells) >= 4 and any(c.isdigit() for c in cells[0]):
                        scraped.append({
                            "symbol": cells[0],
                            "side": cells[1] if len(cells) > 1 else "BUY",
                            "quantity": cells[2] if len(cells) > 2 else 0,
                            "price": cells[3] if len(cells) > 3 else 0,
                        })
                except Exception:
                    continue
            browser.close()
    except Exception as exc:
        return {"ok": False, "attempted": True, "message": str(exc)}

    fills_imported = 0
    if scraped:
        from gateway.brokers.reconciliation import import_fills
        result = import_fills(scraped, broker=broker_id)
        fills_imported = result.get("imported", 0)

    return {
        "ok": bool(scraped),
        "attempted": True,
        "scraped": len(scraped),
        "fills_imported": fills_imported,
        "message": f"已从券商页面抓取 {len(scraped)} 条成交并导入 {fills_imported} 条" if scraped else "未抓取到成交，请收盘后重试",
    }



def assist_place_order(
    broker_id: str,
    *,
    symbol: str,
    name: str,
    side: str,
    quantity: int,
    limit_price: float,
) -> dict[str, Any]:
    """Reuse saved session → open quote/trade page → pre-fill when possible."""
    market, code, _ = symbol_to_market(symbol)
    urls = build_broker_urls(broker_id, symbol=symbol, name=name, side=side, quantity=quantity, limit_price=limit_price)
    clip = f"{name or symbol} {code} {side} {quantity}股 限价{limit_price:.2f}"

    if not has_saved_session(broker_id) or not _ensure_playwright():
        launch = launch_cn_broker(
            broker_id,
            symbol=symbol,
            name=name,
            side=side,
            quantity=quantity,
            limit_price=limit_price,
            target="trade_login",
        )
        return {
            "ok": True,
            "mode": "browser_launch",
            "message": launch.get("message") + (" · 提示：先点「登录券商一次」可免重复登录" if not has_saved_session(broker_id) else ""),
            "handoff": {
                "mode": "broker_browser",
                "web_url": launch.get("url"),
                "steps": launch.get("next_steps", []),
                "clipboard_hint": clip,
            },
            "need_login_assist": not has_saved_session(broker_id),
        }

    quote_url = urls.get("quote") or urls.get("trade_login", "")
    screenshot_path = SESSION_DIR / f"assist_{code}_{datetime.now(timezone.utc).strftime('%H%M%S')}.png"
    filled = False
    note = ""

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(storage_state=str(session_path(broker_id)))
            page = context.new_page()
            page.goto(quote_url, wait_until="domcontentloaded", timeout=60000)
            page.bring_to_front()
            if broker_id == "eastmoney_manual" and side.upper() == "BUY":
                filled = _try_fill_eastmoney(page, code=code, quantity=quantity, limit_price=limit_price)
            elif side.upper() == "BUY":
                filled = _try_fill_generic_trade(page, code=code, quantity=quantity, limit_price=limit_price)
                if not filled and broker_id == "huatai_zhangle":
                    filled = _try_fill_huatai(page, code=code, quantity=quantity, limit_price=limit_price)
            page.wait_for_timeout(2500)
            try:
                page.screenshot(path=str(screenshot_path), full_page=False)
            except Exception:
                screenshot_path = None
            note = "已用保存的登录态打开行情页" + ("，并尝试预填买入表单" if filled else "，请点击买入并核对")
            browser.close()
    except Exception as exc:
        launch_cn_broker(broker_id, symbol=symbol, name=name, target="quote")
        return {
            "ok": True,
            "mode": "browser_fallback",
            "message": f"会话可能过期，已重新打开页面：{exc}",
            "need_login_assist": True,
        }

    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "broker_id": broker_id,
        "symbol": symbol,
        "quantity": quantity,
        "limit_price": limit_price,
        "filled": filled,
        "screenshot": str(screenshot_path) if screenshot_path else "",
    }
    ASSIST_LOG.parent.mkdir(parents=True, exist_ok=True)
    with ASSIST_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return {
        "ok": True,
        "mode": "playwright_assist",
        "filled": filled,
        "message": note,
        "handoff": {
            "mode": "playwright_assist",
            "web_url": quote_url,
            "clipboard_hint": clip,
            "screenshot": str(screenshot_path) if screenshot_path else "",
            "steps": [
                "浏览器应已携带你的登录态",
                f"核对 {name or symbol}（{code}）",
                f"数量 {quantity} 股、限价 ¥{limit_price:.2f}",
                "点击券商页面的「买入」确认（最后一步由你完成）",
            ],
        },
        "legal_boundary": "USER_FINAL_CONFIRM_ON_BROKER",
    }


def _try_add_watchlist_button(page: Any) -> bool:
    """Best-effort click 加自选 on quote pages — DOM varies."""
    selectors = [
        "text=加自选",
        "text=加入自选",
        "text=添加自选",
        "button:has-text('自选')",
        "[title*='自选']",
        ".addZXG",
        "#addFavor",
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible(timeout=800):
                loc.click(timeout=2000)
                page.wait_for_timeout(600)
                return True
        except Exception:
            continue
    return False


def assist_sync_watchlist(
    broker_id: str,
    items: list[dict[str, Any]],
    *,
    max_symbols: int = 15,
) -> dict[str, Any]:
    """Sync favorites to broker watchlist — session reuse + CSV export fallback."""
    from gateway.brokers.cn_broker_registry import CN_BROKER_ECOSYSTEM

    if not items:
        return {"ok": False, "error": "EMPTY_WATCHLIST", "message": "收藏列表为空"}

    spec = CN_BROKER_ECOSYSTEM.get(broker_id) or CN_BROKER_ECOSYSTEM["eastmoney_manual"]
    export_dir = ROOT / "data" / "gateway" / "watchlist_exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d")
    csv_path = export_dir / f"{broker_id}_{ts}_watchlist.csv"
    lines = ["证券代码,证券名称"]
    for it in items[:max_symbols]:
        sym = it.get("symbol", "")
        code = sym.split(".")[0] if sym else ""
        lines.append(f"{code},{it.get('name', '')}")
    csv_path.write_text("\n".join(lines), encoding="utf-8-sig")

    synced: list[str] = []
    attempted: list[str] = []
    playwright_used = False

    if has_saved_session(broker_id) and _ensure_playwright():
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                context = browser.new_context(storage_state=str(session_path(broker_id)))
                page = context.new_page()
                for it in items[:max_symbols]:
                    sym = it.get("symbol", "")
                    if not sym:
                        continue
                    attempted.append(sym)
                    urls = build_broker_urls(broker_id, symbol=sym, name=it.get("name", ""))
                    quote_url = urls.get("quote") or urls.get("trade_login", "")
                    if not quote_url:
                        continue
                    try:
                        page.goto(quote_url, wait_until="domcontentloaded", timeout=45000)
                        page.bring_to_front()
                        if _try_add_watchlist_button(page):
                            synced.append(sym)
                        page.wait_for_timeout(800)
                    except Exception:
                        continue
                browser.close()
            playwright_used = True
        except Exception:
            playwright_used = False

    if not synced:
        opened = []
        for it in items[:min(5, max_symbols)]:
            r = launch_cn_broker(broker_id, symbol=it["symbol"], name=it.get("name", ""), target="quote")
            if r.get("ok"):
                opened.append(it["symbol"])
        return {
            "ok": True,
            "mode": "watchlist_assist_partial" if playwright_used else "watchlist_csv_and_tabs",
            "broker_id": broker_id,
            "broker_label": spec["label"],
            "synced": synced,
            "opened": opened,
            "attempted": attempted,
            "csv_file": str(csv_path),
            "message": (
                f"已导出 {len(items)} 只自选 CSV；"
                + (f"自动加自选 {len(synced)} 只；" if synced else "")
                + (f"并打开 {len(opened)} 只行情页供你确认。" if opened else "请在券商 App 导入 CSV 或手动加自选。")
            ),
            "steps": [
                f"CSV 文件：{csv_path.name}（可导入部分券商客户端）",
                spec.get("watchlist_hint", "在行情页点击「加自选」"),
                "同步后可在智能选股继续一键提交订单",
            ],
            "need_login_assist": not has_saved_session(broker_id),
        }

    return {
        "ok": True,
        "mode": "watchlist_playwright_assist",
        "broker_id": broker_id,
        "broker_label": spec["label"],
        "synced": synced,
        "attempted": attempted,
        "csv_file": str(csv_path),
        "message": f"已通过浏览器助手将 {len(synced)} 只加入 {spec['label']} 自选（共 {len(attempted)} 只尝试）",
        "steps": ["请在券商页面确认自选列表已更新", f"备用 CSV：{csv_path.name}"],
    }


def _try_fill_generic_trade(page: Any, *, code: str, quantity: int, limit_price: float) -> bool:
    """Generic trade form fill — works on many Chinese broker web UIs."""
    try:
        for sel in ["text=买入", "button:has-text('买入')", "a:has-text('买入')"]:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible(timeout=1000):
                loc.click(timeout=2000)
                page.wait_for_timeout(800)
                break
    except Exception:
        pass
    selectors_code = [
        "input[placeholder*='代码']", "input[placeholder*='证券']", "input[placeholder*='股票']",
        "#stockCode", "input[name='stockcode']", "input[name='stockCode']",
    ]
    selectors_qty = ["input[placeholder*='数量']", "#buyAmount", "input[name='amount']", "input[name='volume']"]
    selectors_price = ["input[placeholder*='价格']", "#buyPrice", "input[name='price']"]
    filled_any = False
    try:
        for sel in selectors_code:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible(timeout=500):
                loc.fill(code)
                filled_any = True
                break
        for sel in selectors_price:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible(timeout=500):
                loc.fill(f"{limit_price:.2f}")
                filled_any = True
                break
        for sel in selectors_qty:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible(timeout=500):
                loc.fill(str(quantity))
                return True
    except Exception:
        return filled_any
    return filled_any


def _try_fill_huatai(page: Any, *, code: str, quantity: int, limit_price: float) -> bool:
    """华泰网厅专用填单尝试。"""
    try:
        for sel in ["text=买入", "text=普通买入"]:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible(timeout=1500):
                loc.click(timeout=2000)
                page.wait_for_timeout(1000)
                break
    except Exception:
        pass
    return _try_fill_generic_trade(page, code=code, quantity=quantity, limit_price=limit_price)


def _try_fill_eastmoney(page: Any, *, code: str, quantity: int, limit_price: float) -> bool:
    """Best-effort fill on Eastmoney pages — DOM varies, never auto-submit."""
    selectors_code = [
        "input[placeholder*='代码']",
        "input[placeholder*='证券']",
        "#stockCode",
        "input[name='stockcode']",
    ]
    selectors_qty = ["input[placeholder*='数量']", "#buyAmount", "input[name='amount']"]
    selectors_price = ["input[placeholder*='价格']", "#buyPrice", "input[name='price']"]
    try:
        for sel in selectors_code:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible():
                loc.fill(code)
                break
        for sel in selectors_price:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible():
                loc.fill(f"{limit_price:.2f}")
                break
        for sel in selectors_qty:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible():
                loc.fill(str(quantity))
                return True
    except Exception:
        return False
    return False


def _try_auto_submit(page: Any) -> bool:
    """Click broker confirm/submit — only when gates allow browser_auto_submit."""
    from gateway.live_trading.gates import load_gates
    if not load_gates().browser_auto_submit:
        return False
    submit_selectors = [
        "text=确认买入",
        "text=买入确认",
        "button:has-text('确认')",
        "button:has-text('提交')",
        "text=下单",
        "#btnBuy",
        ".confirm-btn",
    ]
    for sel in submit_selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible(timeout=800):
                loc.click(timeout=3000)
                page.wait_for_timeout(1500)
                return True
        except Exception:
            continue
    return False


def assist_place_order_auto(
    broker_id: str,
    *,
    symbol: str,
    name: str,
    side: str,
    quantity: int,
    limit_price: float,
    auto_submit: bool = True,
) -> dict[str, Any]:
    """Unattended path: session → trade page → fill → optional auto-submit."""
    from gateway.live_trading.gates import load_gates

    gates = load_gates()
    if auto_submit and not gates.browser_auto_submit:
        auto_submit = False

    market, code, _ = symbol_to_market(symbol)
    urls = build_broker_urls(broker_id, symbol=symbol, name=name, side=side, quantity=quantity, limit_price=limit_price)

    if not has_saved_session(broker_id):
        login = run_login_assist(broker_id, wait_seconds=60)
        if not login.get("logged_in_detected"):
            return {
                "ok": False,
                "error": {"code": "NO_SESSION", "message": "无登录会话，无人值守中止"},
                "need_login_assist": True,
            }

    trade_url = urls.get("trade_login") or urls.get("quote", "")
    filled = submitted = False
    screenshot_path = SESSION_DIR / f"auto_{code}_{datetime.now(timezone.utc).strftime('%H%M%S')}.png"

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=gates.browser_auto_submit)
            context = browser.new_context(storage_state=str(session_path(broker_id)))
            page = context.new_page()
            page.goto(trade_url, wait_until="domcontentloaded", timeout=60000)
            page.bring_to_front()
            if broker_id == "eastmoney_manual":
                filled = _try_fill_eastmoney(page, code=code, quantity=quantity, limit_price=limit_price)
            else:
                filled = _try_fill_generic_trade(page, code=code, quantity=quantity, limit_price=limit_price)
                if not filled:
                    filled = _try_fill_huatai(page, code=code, quantity=quantity, limit_price=limit_price)
            if auto_submit and filled:
                submitted = _try_auto_submit(page)
            try:
                page.screenshot(path=str(screenshot_path), full_page=False)
            except Exception:
                screenshot_path = None
            browser.close()
    except Exception as exc:
        return {"ok": False, "error": {"code": "PLAYWRIGHT_AUTO_FAIL", "message": str(exc)[:200]}}

    status = "AUTO_SUBMITTED" if submitted else ("FILLED_PENDING_CONFIRM" if filled else "OPENED_TRADE_PAGE")
    return {
        "ok": True,
        "mode": "playwright_auto",
        "filled": filled,
        "auto_submitted": submitted,
        "order": {"symbol": symbol, "quantity": quantity, "limit_price": limit_price, "status": status},
        "handoff": {
            "mode": "playwright_auto",
            "web_url": trade_url,
            "screenshot": str(screenshot_path) if screenshot_path else "",
        },
        "message": (
            "已自动提交委托" if submitted else
            "已预填订单，请在券商页确认" if filled else
            "已打开交易页"
        ),
        "legal_boundary": "AUTO_SUBMIT_BROWSER" if submitted else "USER_FINAL_CONFIRM_ON_BROKER",
    }
