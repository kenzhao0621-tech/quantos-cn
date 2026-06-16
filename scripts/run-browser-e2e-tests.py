#!/usr/bin/env python3
"""Browser E2E via Playwright — login, buttons, business outcomes."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / ".venv-china-quant" / "bin" / "python"
REPORT_DIR = ROOT / "docs" / "ai" / "app"
SHOT_DIR = REPORT_DIR / "screenshots"
BASE = "http://127.0.0.1:8787"


def _ensure_server() -> None:
    subprocess.run(["bash", str(ROOT / "scripts/start-portal.sh")], cwd=str(ROOT), check=False)
    for _ in range(20):
        r = subprocess.run(["curl", "-sf", f"{BASE}/health"], capture_output=True)
        if r.returncode == 0:
            return
        time.sleep(0.5)
    raise RuntimeError("server not ready")


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    cases: list[dict] = []

    # Reset demo state via API when possible (avoid direct risk-control file deletion)
    try:
        import urllib.request
        import json as _json
        req = urllib.request.Request(
            f"{BASE}/api/v1/risk/reset-confirm",
            data=b"{}",
            method="POST",
            headers={"X-API-Key": "dev-service-risk-key", "Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass

    _ensure_server()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        subprocess.run([str(PY), "-m", "pip", "install", "playwright", "-q"], check=False)
        subprocess.run([str(PY), "-m", "playwright", "install", "chromium"], check=False)
        from playwright.sync_api import sync_playwright

    js_errors: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.on("pageerror", lambda err: js_errors.append(str(err)))

        def shot(name: str) -> str:
            path = SHOT_DIR / f"{name}.png"
            page.screenshot(path=str(path))
            return str(path)

        # Login
        page.goto(f"{BASE}/portal")
        page.select_option("#login-role", "admin")
        page.click("#btn-login")
        page.wait_for_timeout(1500)
        cases.append({"case": "login", "passed": page.locator("#login-overlay").is_hidden(), "screenshot": shot("01_login")})

        # Overview loaded
        overview = page.locator("#overview-body").inner_text()
        cases.append({"case": "overview", "passed": "mode" in overview.lower() or "PAPER" in overview or "RESEARCH" in overview, "screenshot": shot("02_overview")})

        # System doctor
        page.click('[data-action="doctor"]')
        page.wait_for_timeout(2000)
        log = page.locator("#action-log-body").inner_text()
        cases.append({"case": "doctor", "passed": "passed" in log and "request_id" in log, "screenshot": shot("03_doctor")})

        # Backtest
        page.click('button.tab[data-page="models"]')
        page.wait_for_timeout(300)
        page.click('[data-action="backtest"]')
        page.wait_for_timeout(1500)
        log = page.locator("#action-log-body").inner_text()
        cases.append({"case": "backtest", "passed": "pit_passed" in log or "succeeded" in log, "screenshot": shot("04_backtest")})

        # Paper start/stop — use paper page buttons (visible)
        page.click('button.tab[data-page="paper"]')
        page.wait_for_timeout(300)
        page.locator('#page-paper [data-action="paper-start"]').click()
        page.wait_for_timeout(1000)
        log = page.locator("#action-log-body").inner_text()
        paper_ok = "PAPER_TRADING_ACTIVE" in log or "succeeded" in log
        page.locator('#page-paper [data-action="paper-stop"]').click()
        page.wait_for_timeout(800)
        cases.append({"case": "paper_start_stop", "passed": paper_ok, "screenshot": shot("05_paper")})

        # Shadow start/stop
        page.click('button.tab[data-page="shadow"]')
        page.wait_for_timeout(300)
        page.locator('#page-shadow [data-action="shadow-start"]').click()
        page.wait_for_timeout(1000)
        log = page.locator("#action-log-body").inner_text()
        shadow_ok = "SHADOW_LIVE" in log or "zero_real_orders" in log.lower()
        page.locator('#page-shadow [data-action="shadow-stop"]').click()
        page.wait_for_timeout(800)
        cases.append({"case": "shadow_start_stop", "passed": shadow_ok, "screenshot": shot("06_shadow")})

        # Risk halt + reset — stay on risk page
        page.click('button.tab[data-page="risk"]')
        page.wait_for_timeout(300)
        page.locator('#page-risk [data-action="halt"]').click()
        page.wait_for_timeout(800)
        page.evaluate("async () => { await QuantOSApi.login('service_risk'); }")
        page.wait_for_timeout(500)
        page.locator('#page-risk [data-action="reset-confirm"]').click()
        page.wait_for_timeout(1000)
        log = page.locator("#action-log-body").inner_text()
        cases.append({"case": "risk_halt_reset", "passed": "reset" in log.lower() or "succeeded" in log, "screenshot": shot("07_risk")})

        # vnpy start
        page.click('button.tab[data-page="overview"]')
        page.click("#btn-vnpy-start")
        page.wait_for_timeout(1000)
        vnpy = page.locator("#vnpy-status").inner_text()
        cases.append({"case": "vnpy_start", "passed": "running" in vnpy.lower() or "started" in vnpy.lower() or "true" in vnpy.lower(), "screenshot": shot("08_vnpy")})

        cases.append({"case": "no_js_errors", "passed": len(js_errors) == 0, "errors": js_errors})

        browser.close()

    passed = all(c["passed"] for c in cases)
    report = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "cases": cases,
        "js_errors": js_errors,
        "screenshot_dir": str(SHOT_DIR),
        "overall_passed": passed,
    }
    (REPORT_DIR / "07_BROWSER_E2E_REPORT.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (REPORT_DIR / "07_BROWSER_E2E_REPORT.md").write_text(
        f"# Browser E2E\n\n- Overall: **{'PASS' if passed else 'FAIL'}**\n"
        + "\n".join(f"- {c['case']}: {'PASS' if c['passed'] else 'FAIL'}" for c in cases),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2))
    subprocess.run(["bash", str(ROOT / "scripts/stop-portal.sh")], cwd=str(ROOT))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
