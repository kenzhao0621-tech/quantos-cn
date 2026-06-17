#!/usr/bin/env python3
"""V6 fresh-browser E2E — business semantics across vertical slices.

Connects to an already-running portal on 8787. Uses a brand-new Chromium context
(no cookies/storage/SW), captures HAR + per-slice screenshots, and asserts real
business outcomes — not HTTP 200 or element existence.

Slices: 1) system/login  2) market data  3) async job  4) paper trading
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "ai" / "v6"
SHOT = OUT / "screenshots"
HAR_DIR = OUT / "har"
BASE = "http://127.0.0.1:8787"

CHECKS: list[dict] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    CHECKS.append({"name": name, "passed": bool(cond), "detail": detail})
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def main() -> int:
    from playwright.sync_api import sync_playwright

    SHOT.mkdir(parents=True, exist_ok=True)
    HAR_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    har_path = HAR_DIR / f"portal_v6_{stamp}.har"

    js_errors: list[str] = []
    api_404: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(record_har_path=str(har_path))
        page = context.new_page()
        page.on("console", lambda m: js_errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: js_errors.append(str(e)))
        page.on(
            "response",
            lambda r: api_404.append(r.url) if (r.status == 404 and "/api/" in r.url) else None,
        )

        # ---- Slice 1: system + login --------------------------------------
        page.goto(f"{BASE}/portal", wait_until="networkidle")
        page.select_option("#login-role", "admin")
        page.click("#btn-login")
        page.wait_for_selector("#login-overlay.hidden", state="attached", timeout=10000)
        check("Slice1: login succeeds (app visible)", page.is_hidden("#login-overlay"))
        page.wait_for_timeout(1500)
        page.screenshot(path=str(SHOT / "01_overview.png"), full_page=True)

        footer = page.text_content("#footer-version") or ""
        check("Slice1: footer shows backend+frontend build", "Backend" in footer and "Frontend" in footer, footer[:80])
        warn_hidden = page.is_hidden("#footer-build-warn")
        check("Slice1: NO build mismatch warning", warn_hidden)

        # ---- Slice 2: market data -----------------------------------------
        page.click('.tab[data-page="market"]')
        page.wait_for_timeout(500)
        page.click('[data-action="market-refresh"]')
        page.wait_for_timeout(1500)
        page.screenshot(path=str(SHOT / "02_market.png"), full_page=True)

        summary = page.text_content("#market-summary") or ""
        check("Slice2: market NOT blocked (no BLOCKED_BY_DATA)", "数据被阻断" not in summary and "BLOCKED" not in summary, summary[:80])
        idx_rows = page.query_selector_all("#market-indices table.data-table tbody tr")
        check("Slice2: indices table has real rows", len(idx_rows) >= 1, f"rows={len(idx_rows)}")
        prov_rows = page.query_selector_all("#market-providers table.data-table tbody tr")
        check("Slice2: provider health rows present", len(prov_rows) >= 1, f"rows={len(prov_rows)}")
        cov_rows = page.query_selector_all("#market-coverage table.data-table tbody tr")
        check("Slice2: data coverage rows present", len(cov_rows) >= 1, f"rows={len(cov_rows)}")
        # raw JSON detection in primary views
        raw = page.evaluate(
            """() => {
              let n = 0;
              document.querySelectorAll('[data-primary-view], .primary-view').forEach((b) => {
                const t = (b.textContent || '').trim();
                if (t.startsWith('{') && t.includes('\"mode\"')) n++;
                if (t.startsWith('[') && t.length > 200) n++;
              });
              return n;
            }"""
        )
        check("Slice2: zero raw JSON in primary views", raw == 0, f"raw_blocks={raw}")

        # ---- Slice 3: async job (real progress + terminal state) ----------
        page.click('[data-action="market-update-job"]')
        # poll the job panel up to ~60s for a terminal badge
        terminal = ""
        for _ in range(70):
            page.wait_for_timeout(1000)
            badge = page.query_selector("#market-job .job-panel .badge")
            txt = (badge.text_content() if badge else "") or ""
            if txt in ("SUCCEEDED", "FAILED", "CANCELLED"):
                terminal = txt
                break
        page.screenshot(path=str(SHOT / "03_job.png"), full_page=True)
        check("Slice3: async job reached terminal state", terminal in ("SUCCEEDED", "FAILED"), f"state={terminal}")
        pct = page.text_content("#market-job .job-progress-fill") or ""
        check("Slice3: job progress bar populated", "%" in pct, pct.strip())
        events = page.query_selector_all("#market-job .job-event")
        check("Slice3: job emitted step events", len(events) >= 1, f"events={len(events)}")

        # ---- Slice 4: paper trading mode change ---------------------------
        page.click('.tab[data-page="paper"]')
        page.wait_for_timeout(400)
        # reset to a clean RESEARCH_ONLY baseline first (idempotent)
        page.locator('[data-action="paper-stop"]').locator("visible=true").first.click()
        page.wait_for_timeout(1000)
        mode_before = page.text_content("#mode-pill") or ""
        page.locator('[data-action="paper-start"]').locator("visible=true").first.click()
        page.wait_for_timeout(1800)
        mode_after = page.text_content("#mode-pill") or ""
        page.screenshot(path=str(SHOT / "04_paper.png"), full_page=True)
        check("Slice4: paper start changes mode RESEARCH->PAPER",
              ("研究" in mode_before or "RESEARCH" in mode_before.upper()) and ("模拟" in mode_after or "PAPER" in mode_after.upper()),
              f"{mode_before} -> {mode_after}")
        # reset back to research-only
        page.locator('[data-action="paper-stop"]').locator("visible=true").first.click()
        page.wait_for_timeout(800)

        context.close()
        browser.close()

    check("Global: no JS console errors", len(js_errors) == 0, f"errors={js_errors[:3]}")
    check("Global: no API 404s", len(api_404) == 0, f"404s={api_404[:3]}")

    passed = all(c["passed"] for c in CHECKS)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overall_passed": passed,
        "checks": CHECKS,
        "js_errors": js_errors,
        "api_404": api_404,
        "har": str(har_path),
        "screenshots": [str(p) for p in sorted(SHOT.glob("*.png"))],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "10_FRESH_BROWSER_E2E.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n{'ALL PASS' if passed else 'FAILURES'} — {sum(c['passed'] for c in CHECKS)}/{len(CHECKS)}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
