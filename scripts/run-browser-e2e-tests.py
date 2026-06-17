#!/usr/bin/env python3
"""Browser E2E via Playwright — login, buttons, business outcomes."""

from __future__ import annotations

import json
import os
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
    for _ in range(10):
        r = subprocess.run(["curl", "-sf", f"{BASE}/health"], capture_output=True)
        if r.returncode == 0:
            return
        time.sleep(0.3)
    subprocess.run(["bash", str(ROOT / "scripts/start-portal.sh")], cwd=str(ROOT), check=False)
    for _ in range(30):
        r = subprocess.run(["curl", "-sf", f"{BASE}/health"], capture_output=True)
        if r.returncode == 0:
            return
        time.sleep(0.5)
    raise RuntimeError("server not ready")


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    cases: list[dict] = []

    # Reset demo state via API when server is up
    _ensure_server()
    try:
        import urllib.request

        req = urllib.request.Request(
            f"{BASE}/api/v1/risk/reset-confirm",
            data=b"{}",
            method="POST",
            headers={"X-API-Key": "dev-service-risk-key", "Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        subprocess.run([str(PY), "-m", "pip", "install", "playwright", "-q"], check=False)
        from playwright.sync_api import sync_playwright

    # Ensure Chromium is available (CI / fresh venv)
    chk = subprocess.run([str(PY), "-m", "playwright", "install", "chromium"], capture_output=True)
    if chk.returncode != 0:
        print(chk.stderr.decode("utf-8", errors="replace")[-500:])

    js_errors: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.on("pageerror", lambda err: js_errors.append(str(err)))

        def shot(name: str) -> str:
            path = SHOT_DIR / f"{name}.png"
            page.screenshot(path=str(path))
            return str(path)

        # Login — beginner investor (default product persona)
        page.goto(f"{BASE}/portal")
        page.select_option("#login-role", "investor")
        page.click("#btn-login")
        if page.locator("#legal-overlay").is_visible():
            page.click("#btn-legal-accept")
            page.wait_for_timeout(300)
        page.wait_for_selector("#beginner-steps", state="visible", timeout=15000)
        page.wait_for_function(
            """() => {
                const steps = document.getElementById('beginner-steps')?.children?.length || 0;
                const role = document.getElementById('role-pill')?.innerText || '';
                return steps >= 4 && role.includes('新手');
            }""",
            timeout=15000,
        )
        cases.append({"case": "login", "passed": page.locator("#login-overlay").is_hidden(), "screenshot": shot("01_login")})

        # Beginner guide loaded
        steps = page.locator("#beginner-steps .beginner-step-card").count()
        cases.append({"case": "beginner_guide", "passed": steps >= 4, "screenshot": shot("02_guide")})

        # Overview (advanced) still works
        page.click('button.tab[data-page="overview"]')
        page.wait_for_selector("#overview-body", state="visible", timeout=10000)
        overview = page.locator("#overview-body").inner_text()
        cases.append({"case": "overview", "passed": "mode:" in overview and ("PAPER" in overview or "RESEARCH" in overview), "screenshot": shot("03_overview")})

        # System doctor
        page.click('[data-action="doctor"]')
        page.wait_for_timeout(3000)
        log = page.locator("#action-log-body").inner_text()
        cases.append({
            "case": "doctor",
            "passed": ("检查通过" in log or "passed" in log.lower()) and ("Run ID" in log or "run_id" in log),
            "screenshot": shot("04_doctor"),
        })

        # Broker connect — investor must not get 403
        page.click('button.tab[data-page="brokers"]')
        page.wait_for_timeout(500)
        page.locator('#page-brokers [data-action="broker-connect"]').click()
        page.wait_for_timeout(3000)
        log = page.locator("#action-log-body").inner_text()
        broker_ok = "403" not in log and ("券商连接" in log or "券商已连接" in log or "succeeded" in log.lower() or "已打开" in log)
        cases.append({"case": "broker_connect", "passed": broker_ok, "screenshot": shot("05_broker")})

        # Help / disclaimer page
        page.click('button.tab[data-page="help"]')
        page.wait_for_timeout(500)
        page.click('.help-nav-btn[data-help-section="legal"]')
        page.wait_for_timeout(300)
        help_text = page.locator("#help-content").inner_text()
        cases.append({
            "case": "help_disclaimer",
            "passed": "免责" in help_text or "不构成投资建议" in page.locator("#page-help").inner_text(),
            "screenshot": shot("06_help"),
        })

        # Paper start/stop — use paper page buttons (visible)
        page.click('button.tab[data-page="paper"]')
        page.wait_for_timeout(300)
        page.locator('#page-paper [data-action="paper-start"]').click()
        page.wait_for_timeout(2000)
        log = page.locator("#action-log-body").inner_text()
        paper_ok = "PAPER_TRADING" in log or "模拟交易" in log or "成功" in log
        page.locator('#page-paper [data-action="paper-stop"]').click()
        page.wait_for_timeout(1500)
        cases.append({"case": "paper_start_stop", "passed": paper_ok, "screenshot": shot("07_paper")})

        # Shadow start/stop (advanced tab if present)
        if page.locator('button.tab[data-page="shadow"]').count():
            page.click('button.tab[data-page="shadow"]')
            page.wait_for_timeout(300)
            page.locator('#page-shadow [data-action="shadow-start"]').click()
            page.wait_for_timeout(2000)
            log = page.locator("#action-log-body").inner_text()
            shadow_ok = "SHADOW" in log or "影子" in log or "零真实订单" in log or "成功" in log
            page.locator('#page-shadow [data-action="shadow-stop"]').click()
            page.wait_for_timeout(800)
            cases.append({"case": "shadow_start_stop", "passed": shadow_ok, "screenshot": shot("08_shadow")})

        # Risk halt + reset — optional advanced
        if page.locator('button.tab[data-page="risk"]').count():
            page.click('button.tab[data-page="risk"]')
            page.wait_for_timeout(300)
            page.locator('#page-risk [data-action="halt"]').click()
            page.wait_for_timeout(800)
            page.evaluate("async () => { await QuantOSApi.login('service_risk'); }")
            page.wait_for_timeout(500)
            page.locator('#page-risk [data-action="reset-confirm"]').click()
            page.wait_for_timeout(1000)
            log = page.locator("#action-log-body").inner_text()
            cases.append({"case": "risk_halt_reset", "passed": "reset" in log.lower() or "succeeded" in log, "screenshot": shot("09_risk")})

        # vnpy start (advanced overview)
        if page.locator("#btn-vnpy-start").count():
            page.click('button.tab[data-page="overview"]')
            page.click("#btn-vnpy-start")
            page.wait_for_timeout(1000)
            vnpy = page.locator("#vnpy-status").inner_text()
            cases.append({"case": "vnpy_start", "passed": "running" in vnpy.lower() or "started" in vnpy.lower() or "true" in vnpy.lower(), "screenshot": shot("10_vnpy")})

        cases.append({"case": "no_js_errors", "passed": len(js_errors) == 0, "errors": js_errors})

        browser.close()

    critical_cases = {"login", "beginner_guide", "broker_connect", "help_disclaimer", "doctor", "no_js_errors"}
    critical_passed = all(c["passed"] for c in cases if c["case"] in critical_cases)
    passed = all(c["passed"] for c in cases)
    report = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "cases": cases,
        "js_errors": js_errors,
        "screenshot_dir": str(SHOT_DIR),
        "critical_e2e_passed": critical_passed,
        "overall_passed": passed,
    }
    (REPORT_DIR / "07_BROWSER_E2E_REPORT.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (ROOT / "artifacts" / "e2e_results.json").write_text(json.dumps({
        "generated_at": report["generated_at"],
        "critical_e2e_passed": critical_passed,
        "all_passed": passed,
        "cases": cases,
    }, indent=2), encoding="utf-8")
    (REPORT_DIR / "07_BROWSER_E2E_REPORT.md").write_text(
        f"# Browser E2E\n\n- Overall: **{'PASS' if passed else 'FAIL'}**\n"
        + "\n".join(f"- {c['case']}: {'PASS' if c['passed'] else 'FAIL'}" for c in cases),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2))
    if os.environ.get("QUANTOS_E2E_STOP_SERVER", "").lower() in {"1", "true", "yes"}:
        subprocess.run(["bash", str(ROOT / "scripts/stop-portal.sh")], cwd=str(ROOT))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
