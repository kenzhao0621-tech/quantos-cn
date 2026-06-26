#!/usr/bin/env python3
"""Portal truth audit — every tab and every actionable button."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / ".venv-china-quant" / "bin" / "python"
BASE = "http://127.0.0.1:8787"
OUT_JSON = ROOT / "docs" / "ai" / "final" / "04_PORTAL_FAILURE_ROOT_CAUSE.json"
OUT_MD = ROOT / "docs" / "ai" / "final" / "04_PORTAL_FAILURE_ROOT_CAUSE.md"
SHOT_DIR = ROOT / "docs" / "ai" / "final" / "screenshots" / "portal-audit"

# data-action -> expected API prefix (None = client-only / variable)
ACTION_API_HINT: dict[str, str | None] = {
    "doctor": "/api/v1/system/doctor",
    "market-update": "/api/v1/market/update",
    "daily-run": "/api/v1/research/daily-run",
    "risk-check": "/api/v1/risk/status",
    "paper-start": "/api/v1/paper/start",
    "paper-stop": "/api/v1/paper/stop",
    "shadow-start": "/api/v1/shadow/start",
    "shadow-stop": "/api/v1/shadow/stop",
    "halt": "/api/v1/risk/halt",
    "reset-request": "/api/v1/risk/reset-request",
    "reset-confirm": "/api/v1/risk/reset-confirm",
    "backtest": "/api/v1/research/backtest",
    "candidate-gate": "/api/v1/research/candidate",
    "market-refresh": "/api/v1/market/",
    "paper-refresh": "/api/v1/paper/",
    "open-pdf": "/api/v1/system/status",
    "open-json": "/api/v1/research/reports",
}

BTN_API_HINT: dict[str, str] = {
    "btn-vnpy-start": "/api/v1/quantos/vnpy/start",
    "btn-vnpy-stop": "/api/v1/quantos/vnpy/stop",
    "btn-qlib-baseline": "/api/v1/quantos/qlib/baseline",
    "btn-qlib-baseline-models": "/api/v1/quantos/qlib/baseline",
    "btn-login": "/api/v1/auth/login",
    "btn-logout": None,  # type: ignore[assignment]
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _health_ok() -> bool:
    try:
        with urllib.request.urlopen(f"{BASE}/health", timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


def _ensure_playwright():
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401

        return sync_playwright
    except ImportError:
        subprocess.run([str(PY), "-m", "pip", "install", "playwright", "-q"], check=False)
        subprocess.run([str(PY), "-m", "playwright", "install", "chromium"], check=False)
        from playwright.sync_api import sync_playwright

        return sync_playwright


def _ensure_server() -> bool:
    """Return True if we started the server (caller may stop only if needed)."""
    if _health_ok():
        return False
    subprocess.run(["bash", str(ROOT / "scripts/start-portal.sh")], cwd=str(ROOT), check=False)
    for _ in range(40):
        if _health_ok():
            return True
        time.sleep(0.5)
    raise RuntimeError("Portal did not become healthy on port 8787")


def _reset_risk() -> None:
    try:
        req = urllib.request.Request(
            f"{BASE}/api/v1/risk/reset-confirm",
            data=b"{}",
            method="POST",
            headers={"X-API-Key": "dev-service-risk-key", "Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def _slug(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]+", "_", text.strip())[:80]
    return s or "item"


def _parse_action_log(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}


def _classify(rec: dict[str, Any]) -> str:
    if not rec.get("click_succeeded"):
        if rec.get("skipped_reason"):
            return "SKIPPED_NOT_VISIBLE"
        return "CLICK_FAILED"

    js = rec.get("js_errors") or []
    if js:
        return "JS_RUNTIME_ERROR"

    api_reqs = [r for r in rec.get("network_requests") or [] if "/api/" in r.get("url", "")]
    statuses = [int(r.get("status") or 0) for r in api_reqs if r.get("status") is not None]

    if statuses:
        if any(s == 404 for s in statuses):
            return "API_ROUTE_MISSING"
        if any(s == 403 for s in statuses):
            return "API_AUTH_DENIED"
        if any(s >= 500 for s in statuses):
            return "API_SERVER_ERROR"
        if any(s >= 400 for s in statuses):
            return "API_CLIENT_ERROR"

    hint = rec.get("expected_api_hint")
    action = rec.get("action_key") or ""
    client_only = action in ("open-pdf", "btn-logout") or hint is None

    if hint and not client_only and not api_reqs:
        return "FRONTEND_EVENT_NOT_BOUND"

    ui = rec.get("ui_change") or {}
    if rec.get("paper_panels_changed"):
        return "SUCCESS"
    if not client_only and not ui.get("action_log_changed") and not ui.get("page_body_changed"):
        if action not in ("btn-logout",):
            return "UI_NO_FEEDBACK"

    parsed = rec.get("action_log_parsed")
    if isinstance(parsed, dict) and parsed.get("ok") is False:
        return "API_BUSINESS_FAILURE"

    if rec.get("dialog_message"):
        if action == "open-pdf" and "PDF" in rec["dialog_message"]:
            return "SUCCESS"  # expected when no report yet

    if api_reqs and statuses and all(200 <= s < 300 for s in statuses):
        if isinstance(parsed, dict) and parsed.get("ok") is True:
            return "SUCCESS"
        if parsed is None and ui.get("action_log_changed"):
            return "SUCCESS"
        if client_only:
            return "SUCCESS"

    if not api_reqs and client_only and (ui.get("action_log_changed") or action == "btn-logout"):
        return "SUCCESS"

    if isinstance(parsed, dict) and parsed.get("ok") is True:
        return "SUCCESS"

    return "UNKNOWN_FAILURE"


def _audit_button(page, tab_page: str, tab_label: str, button_index: int, selector: str, label: str, action_key: str) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "page": tab_page,
        "tab_label": tab_label,
        "label": label,
        "button_index": button_index,
        "selector": selector,
        "action_key": action_key,
        "click_succeeded": False,
        "skipped_reason": None,
        "network_requests": [],
        "js_errors": [],
        "ui_change": {},
        "action_log_before": "",
        "action_log_after": "",
        "action_log_parsed": None,
        "dialog_message": None,
        "screenshot": None,
        "expected_api_hint": ACTION_API_HINT.get(action_key) or BTN_API_HINT.get(action_key),
    }

    scope = page.locator(f"#page-{tab_page}")
    loc = scope.locator('button[data-action], button[id^="btn-"]').nth(button_index)
    try:
        if loc.count() == 0:
            rec["skipped_reason"] = "not_in_dom"
            return rec
        if not loc.is_visible():
            rec["skipped_reason"] = "not_visible"
            return rec
    except Exception as exc:
        rec["skipped_reason"] = f"visibility_check_failed: {exc}"
        return rec

    page_body_sel = f"#page-{tab_page}"
    before_log = page.locator("#action-log-body").inner_text(timeout=3000)
    before_body = ""
    try:
        before_body = page.locator(page_body_sel).inner_text(timeout=2000)
    except Exception:
        before_body = ""

    net_events: list[dict[str, Any]] = []
    js_local: list[str] = []
    dialog_msg: list[str] = []

    def on_request(req):
        if "/api/" in req.url:
            net_events.append({"phase": "request", "method": req.method, "url": req.url})

    def on_response(resp):
        if "/api/" in resp.url:
            net_events.append(
                {
                    "phase": "response",
                    "method": resp.request.method,
                    "url": resp.url,
                    "status": resp.status,
                }
            )

    def on_pageerror(err):
        js_local.append(str(err))

    def on_dialog(dialog):
        dialog_msg.append(dialog.message)
        dialog.accept()

    page.on("request", on_request)
    page.on("response", on_response)
    page.on("pageerror", on_pageerror)
    page.on("dialog", on_dialog)

    click_err = None
    try:
        loc.click(timeout=5000)
        wait_ms = 20000 if action_key == "market-update" else (8000 if action_key in ("daily-run", "backtest", "candidate-gate") else 3500)
        page.wait_for_timeout(wait_ms)
        rec["click_succeeded"] = True
    except Exception as exc:
        click_err = str(exc)
        rec["click_error"] = click_err
    finally:
        page.remove_listener("request", on_request)
        page.remove_listener("response", on_response)
        page.remove_listener("pageerror", on_pageerror)
        page.remove_listener("dialog", on_dialog)

    rec["js_errors"] = js_local
    rec["dialog_message"] = dialog_msg[0] if dialog_msg else None

    # Dedupe network by url+status keeping order
    seen = set()
    deduped = []
    for ev in net_events:
        if ev["phase"] != "response":
            continue
        key = (ev["url"], ev.get("status"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(ev)
    rec["network_requests"] = deduped

    after_log = page.locator("#action-log-body").inner_text(timeout=3000)
    after_body = ""
    try:
        after_body = page.locator(page_body_sel).inner_text(timeout=2000)
    except Exception:
        after_body = ""

    rec["action_log_before"] = before_log[:500]
    rec["action_log_after"] = after_log[:2000]
    rec["action_log_parsed"] = _parse_action_log(after_log)
    paper_before = ""
    paper_after = ""
    if action_key == "paper-refresh":
        try:
            paper_before = page.locator("#paper-pnl").inner_text(timeout=1000)
        except Exception:
            pass
    rec["ui_change"] = {
        "action_log_changed": before_log != after_log,
        "page_body_changed": before_body != after_body,
        "before_body_hash": hashlib.sha256(before_body.encode()).hexdigest()[:16],
        "after_body_hash": hashlib.sha256(after_body.encode()).hexdigest()[:16],
    }
    if action_key == "paper-refresh":
        try:
            paper_after = page.locator("#paper-pnl").inner_text(timeout=1000)
        except Exception:
            pass
        rec["paper_panels_changed"] = paper_before != paper_after
        rec["ui_change"]["paper_pnl_changed"] = paper_before != paper_after

    rec["classification"] = _classify(rec)
    if rec["classification"] != "SUCCESS" and rec["classification"] != "SKIPPED_NOT_VISIBLE":
        SHOT_DIR.mkdir(parents=True, exist_ok=True)
        shot = SHOT_DIR / f"{_slug(tab_page)}_{_slug(action_key)}.png"
        try:
            page.screenshot(path=str(shot), full_page=True)
            rec["screenshot"] = str(shot.relative_to(ROOT))
        except Exception as exc:
            rec["screenshot_error"] = str(exc)

    return rec


def main() -> int:
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    SHOT_DIR.mkdir(parents=True, exist_ok=True)

    started_by_us = False
    try:
        started_by_us = _ensure_server()
    except RuntimeError as exc:
        report = {
            "generated_at": _utc_now(),
            "error": str(exc),
            "results": [],
            "summary": {},
        }
        OUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
        OUT_MD.write_text(f"# Portal failure root cause\n\nSetup failed: {exc}\n", encoding="utf-8")
        return 1

    _reset_risk()
    sync_playwright = _ensure_playwright()

    tab_records: list[dict[str, Any]] = []
    button_records: list[dict[str, Any]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(15000)

        page.goto(f"{BASE}/portal", wait_until="domcontentloaded")
        page.wait_for_timeout(500)

        # Admin login (skip auditing btn-login on overlay)
        page.select_option("#login-role", "admin")
        page.click("#btn-login")
        page.wait_for_timeout(1500)
        login_ok = page.locator("#login-overlay").is_hidden()
        tab_records.append(
            {
                "type": "login",
                "page": "login",
                "label": "admin login",
                "click_succeeded": login_ok,
                "classification": "SUCCESS" if login_ok else "CLICK_FAILED",
            }
        )
        if not login_ok:
            browser.close()
            raise RuntimeError("Admin login failed")

        tabs = page.locator("button.tab[data-page]")
        tab_count = tabs.count()
        for i in range(tab_count):
            tab = tabs.nth(i)
            page_id = tab.get_attribute("data-page") or f"tab{i}"
            tab_label = (tab.inner_text() or page_id).strip()
            tab_sel = f'button.tab[data-page="{page_id}"]'

            tab_rec = {"page": page_id, "tab_label": tab_label, "selector": tab_sel, "click_succeeded": False}
            if page_id in ("paper", "shadow"):
                _reset_risk()
                page.wait_for_timeout(400)
            try:
                tab.click()
                page.wait_for_timeout(400)
                visible = page.locator(f"#page-{page_id}").is_visible()
                tab_rec["click_succeeded"] = visible
                tab_rec["classification"] = "SUCCESS" if visible else "UI_NO_FEEDBACK"
            except Exception as exc:
                tab_rec["click_error"] = str(exc)
                tab_rec["classification"] = "CLICK_FAILED"
            tab_records.append(tab_rec)

            scope = page.locator(f"#page-{page_id}")
            buttons = scope.locator('button[data-action], button[id^="btn-"]')
            n = buttons.count()
            for j in range(n):
                btn = buttons.nth(j)
                btn_id = btn.get_attribute("id")
                da = btn.get_attribute("data-action")
                action = da or btn_id or f"btn_{j}"
                label = (btn.inner_text() or action).strip()
                if btn_id:
                    sel = f"#page-{page_id} #{btn_id}"
                elif da:
                    sel = f'#page-{page_id} button[data-action="{da}"]'
                else:
                    sel = f"#page-{page_id} button:nth-of-type({j + 1})"

                if btn_id in ("btn-login",):
                    continue

                rec = _audit_button(page, page_id, tab_label, j, sel, label, action)
                if action in ("halt", "reset-request", "reset-confirm"):
                    _reset_risk()
                    page.wait_for_timeout(500)
                button_records.append(rec)

        # Header logout (global)
        if page.locator("#btn-logout").is_visible():
            button_records.append(
                _audit_button(page, "header", "全局", 0, "#btn-logout", "退出", "btn-logout")
            )

        browser.close()

    for rec in button_records:
        if "classification" not in rec:
            rec["classification"] = _classify(rec)

    failures = [r for r in button_records if r.get("classification") not in ("SUCCESS", "SKIPPED_NOT_VISIBLE")]
    by_class: dict[str, list[dict[str, Any]]] = {}
    for r in failures:
        by_class.setdefault(r["classification"], []).append(r)

    summary = {
        "tabs_tested": len(tab_records),
        "buttons_tested": len(button_records),
        "buttons_skipped": sum(1 for r in button_records if r.get("classification") == "SKIPPED_NOT_VISIBLE"),
        "buttons_success": sum(1 for r in button_records if r.get("classification") == "SUCCESS"),
        "buttons_failed": len(failures),
        "failures_by_classification": {k: len(v) for k, v in sorted(by_class.items())},
    }

    report = {
        "generated_at": _utc_now(),
        "base_url": BASE,
        "started_server": started_by_us,
        "summary": summary,
        "tabs": tab_records,
        "buttons": button_records,
        "failures": failures,
    }

    OUT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    md_lines = [
        "# Portal failure root cause",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Base URL: {BASE}",
        f"- Buttons tested: {summary['buttons_tested']}",
        f"- Success: {summary['buttons_success']}",
        f"- Failed: {summary['buttons_failed']}",
        "",
        "## Failures by classification",
        "",
    ]
    for cls, items in sorted(by_class.items()):
        md_lines.append(f"### {cls} ({len(items)})")
        md_lines.append("")
        for item in items:
            md_lines.append(
                f"- **{item.get('page')}** / {item.get('label')} (`{item.get('action_key')}`) — "
                f"selector `{item.get('selector')}`"
            )
            if item.get("network_requests"):
                md_lines.append(f"  - network: {item['network_requests']}")
            if item.get("js_errors"):
                md_lines.append(f"  - js: {item['js_errors']}")
            if item.get("screenshot"):
                md_lines.append(f"  - screenshot: `{item['screenshot']}`")
        md_lines.append("")

    if not failures:
        md_lines.append("_No failures recorded._")
        md_lines.append("")

    OUT_MD.write_text("\n".join(md_lines), encoding="utf-8")

    print(json.dumps({"summary": summary, "failures_by_classification": summary["failures_by_classification"]}, indent=2))

    subprocess.run(["bash", str(ROOT / "scripts/stop-portal.sh")], cwd=str(ROOT), check=False)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
