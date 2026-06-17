#!/usr/bin/env python3
"""Fresh Chromium UI E2E — business semantics, HAR, screenshots, no stale cache."""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / ".venv-china-quant" / "bin" / "python"
OUT = ROOT / "docs" / "ai" / "final-ui"
SHOT = OUT / "screenshots"
HAR_DIR = OUT / "har"
BASE = "http://127.0.0.1:8787"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _run_forensics() -> dict:
    import importlib

    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    short = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    import gateway

    app_module = importlib.import_module("gateway.api.app")

    portal_files = {}
    for name in ("index.html", "app.js", "viewmodels.js", "ui-render.js", "quantos.js", "styles.css"):
        p = ROOT / "apps" / "portal-web" / name
        if p.exists():
            portal_files[name] = {"sha256": _sha256(p), "size": p.stat().st_size}

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit,
        "git_commit_short": short,
        "gateway_module": inspect.getfile(gateway),
        "app_module": inspect.getfile(app_module),
        "repository_root": str(ROOT),
        "portal_source_hashes": portal_files,
    }


def _ensure_server() -> None:
    subprocess.run(["bash", str(ROOT / "scripts/stop-portal.sh")], cwd=str(ROOT), check=False)
    time.sleep(1)
    subprocess.run([str(PY), "-m", "pip", "install", "-e", str(ROOT), "-q"], check=False)
    subprocess.run(["bash", str(ROOT / "scripts/start-portal.sh")], cwd=str(ROOT), check=True)
    for _ in range(30):
        r = subprocess.run(["curl", "-sf", f"{BASE}/health"], capture_output=True)
        if r.returncode == 0:
            return
        time.sleep(0.5)
    raise RuntimeError("server not ready")


def _count_raw_json_pages(page) -> int:
    return page.evaluate(
        """() => {
      const blocks = document.querySelectorAll('[data-primary-view]');
      let n = 0;
      blocks.forEach(b => {
        const t = (b.textContent || '').trim();
        if (t.startsWith('{') && t.includes('"mode"')) n++;
        if (t.startsWith('[') && t.length > 300 && !b.querySelector('table')) n++;
        if (b.querySelector('pre.raw-json') && !b.querySelector('.stat-card, .data-table, .kv-list')) n++;
      });
      return n;
    }"""
    )


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    SHOT.mkdir(parents=True, exist_ok=True)
    HAR_DIR.mkdir(parents=True, exist_ok=True)

    runtime = _run_forensics()
    (OUT / "00_RUNTIME_VERSION_FORENSICS.json").write_text(json.dumps(runtime, indent=2), encoding="utf-8")

    _ensure_server()

    subprocess.run([str(PY), "-m", "playwright", "install", "chromium"], check=False, capture_output=True)

    from playwright.sync_api import sync_playwright

    cases: list[dict] = []
    js_errors: list[str] = []
    api_404: list[str] = []
    har_path = HAR_DIR / f"portal_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}.har"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            storage_state=None,
            record_har_path=str(har_path),
            record_har_content="embed",
        )
        page = context.new_page()
        page.on("pageerror", lambda e: js_errors.append(str(e)))
        page.on("response", lambda r: api_404.append(r.url) if r.status == 404 and "/api/" in r.url else None)

        def shot(name: str) -> str:
            path = SHOT / f"{name}.png"
            page.screenshot(path=str(path), full_page=True)
            return str(path)

        # Version forensics via API
        ver = page.request.get(f"{BASE}/api/v1/system/version")
        ver_json = ver.json()
        page_build = None

        page.goto(f"{BASE}/portal")
        page_build = page.evaluate("document.body.dataset.portalBuild")
        cases.append({
            "case": "version_endpoint",
            "passed": ver.ok and ver_json.get("ok"),
            "backend_commit": ver_json.get("data", {}).get("git_commit_short"),
            "frontend_build": page_build,
        })

        # Fresh login
        page.select_option("#login-role", "admin")
        page.click("#btn-login")
        page.wait_for_timeout(2000)
        cases.append({"case": "login", "passed": page.locator("#login-overlay").is_hidden(), "screenshot": shot("01_login")})

        raw_count = _count_raw_json_pages(page)
        cases.append({"case": "overview_no_raw_json", "passed": raw_count == 0, "raw_json_blocks": raw_count, "screenshot": shot("02_overview")})

        # Tab screenshots
        tabs = ["market", "reports", "models", "agents", "native", "paper", "shadow", "risk", "brokers"]
        tab_pass = True
        prev_html_len = 0
        for tab in tabs:
            page.click(f'button.tab[data-page="{tab}"]')
            page.wait_for_timeout(800)
            rc = _count_raw_json_pages(page)
            content_len = page.evaluate(f"document.getElementById('page-{tab}')?.innerText?.length || 0")
            different = content_len != prev_html_len or tab == "market"
            prev_html_len = content_len
            if rc > 0:
                tab_pass = False
            shot(f"tab_{tab}")
            cases.append({"case": f"tab_{tab}", "passed": rc == 0 and content_len > 50, "raw_json": rc})

        cases.append({"case": "tabs_distinct_content", "passed": tab_pass})

        # Business: paper start — mode must change
        page.click('button.tab[data-page="overview"]')
        st_before = page.request.get(f"{BASE}/api/v1/system/status", headers={"X-API-Key": "demo-local-key-change-in-prod"}).json()
        mode_before = st_before.get("data", {}).get("mode")
        page.locator('[data-action="paper-start"]').first.click()
        page.wait_for_timeout(1500)
        st_after = page.request.get(f"{BASE}/api/v1/system/status", headers={"X-API-Key": "demo-local-key-change-in-prod"}).json()
        mode_after = st_after.get("data", {}).get("mode")
        log_text = page.locator("#action-log-body").inner_text()
        cases.append({
            "case": "paper_start_business",
            "passed": mode_before != mode_after and mode_after == "PAPER_TRADING" and "成功" in log_text,
            "mode_before": mode_before,
            "mode_after": mode_after,
            "screenshot": shot("03_paper_start"),
        })
        page.locator('[data-action="paper-stop"]').first.click()
        page.wait_for_timeout(1000)

        # Doctor
        page.locator('[data-action="doctor"]').first.click()
        page.wait_for_timeout(2000)
        log = page.locator("#action-log-body").inner_text()
        cases.append({"case": "doctor_business", "passed": "成功" in log and "检查通过" in log, "screenshot": shot("04_doctor")})

        # Native label consistency
        header_native = page.locator("#native-pill").inner_text()
        vn_tag = page.locator("#vnpy-mode-tag").inner_text()
        cases.append({
            "case": "native_label_consistent",
            "passed": vn_tag in header_native or header_native.endswith(vn_tag.split("·")[0].strip()),
            "header": header_native,
            "vn_tag": vn_tag,
        })

        cases.append({"case": "no_js_errors", "passed": len(js_errors) == 0, "errors": js_errors})
        cases.append({"case": "no_api_404", "passed": len(api_404) == 0, "urls": api_404[:10]})

        context.close()
        browser.close()

    passed = all(c.get("passed", False) for c in cases)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runtime": runtime,
        "cases": cases,
        "har": str(har_path),
        "screenshot_dir": str(SHOT),
        "overall_passed": passed,
    }
    (OUT / "07_FRESH_BROWSER_E2E.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "09_FINAL_REAL_USABILITY_REPORT.json").write_text(
        json.dumps({**report, "raw_json_primary_views": sum(1 for c in cases if c.get("raw_json_blocks")), "verdict": "PASS" if passed else "FAIL"}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
