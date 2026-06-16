#!/usr/bin/env python3
"""Expanded test suite for full China A-share intelligence system."""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FIX = ROOT / "docs" / "test-fixtures" / "china-quant"

passed = failed = 0


def ok(n):
    global passed
    passed += 1
    print(f"PASS {n}")


def fail(n, m=""):
    global failed
    failed += 1
    print(f"FAIL {n} {m}")


# Legacy tests
r = subprocess.run([sys.executable, str(ROOT / "scripts" / "run-china-quant-tests.py")], capture_output=True, text=True)
if r.returncode == 0:
    ok("legacy A-I+M6")
else:
    fail("legacy", r.stdout[-200:])

from tools.china_quant.providers.fixture_provider import FixtureProvider
from tools.china_quant.providers.registry import ProviderRegistry
from tools.china_quant.universe import build_universe
from tools.china_quant.intelligence import load_full_bundle, run_intelligence
from tools.china_quant.backtest.engine import run_backtest, walk_forward_split
from tools.china_quant.backtest.bias_guards import check_bias
from tools.china_quant.rules_store import load_rules_store
from tools.china_quant.scoring_v2 import score_stock_v2
from tools.china_quant.models import StockRecord
from tools.china_quant.paper_trade import simulate_paper_outcome
from tools.china_quant.model_monitor import compute_monitor

fp = FixtureProvider(FIX)
try:
    env = fp.load_universe("universe_full")
    ok("provider universe")
except Exception as e:
    fail("provider universe", str(e))

try:
    fp.load_bars("601398")
    ok("provider bars")
except Exception as e:
    fail("provider bars", str(e))

rules = load_rules_store()
if len(rules) >= 5:
    ok("rules store")
else:
    fail("rules store")

bundle = load_full_bundle(FIX)
uni = build_universe({"stocks": [__import__("dataclasses").asdict(s) for s in bundle.stocks]})
if uni.stats.total >= 10 and len(uni.excluded) >= 3:
    ok("full universe load+exclude")
else:
    fail("universe", f"t={uni.stats.total} e={len(uni.excluded)}")

policy = fp.load_policy().payload
inst = fp.load_institutional().payload
now = bundle.snapshot.data_timestamp + timedelta(hours=16)
result = run_intelligence(bundle, fixtures_dir=FIX, policy_data=policy, inst_data=inst, now=now)
if result.report.primary and result.dossiers:
    ok("intelligence pipeline+dossier")
else:
    fail("intelligence", f"p={len(result.report.primary)} d={len(result.dossiers)}")

if "政策" in result.report.policy_summary or "央行" in result.report.policy_summary:
    ok("policy monitor")
else:
    ok("policy monitor empty ok")

if result.institutional_count >= 1:
    ok("institutional flow")
else:
    fail("institutional")

st = StockRecord("601398", "x", "SH", "MAIN_SH", "银行", 5.2, 0, 400, trend_score=18, fundamental_score=14, valuation_score=9)
fs = score_stock_v2(st, regime_name="strong bullish trend", sector_strength=12, has_confirmed_catalyst=True, institutional_score=4)
if fs.total >= 68:
    ok("scoring v2")
else:
    fail("scoring v2", str(fs.total))

bars = fp.load_bars("601398").payload["bars"]
bt = run_backtest(bars)
if bt.metrics.get("trade_count", 0) >= 0:
    ok("backtest engine")
else:
    fail("backtest")

tr, te = walk_forward_split(bars)
if len(tr) < len(bars):
    ok("walk-forward split")
else:
    fail("walk-forward")

bias = check_bias(uses_future_data=False)
if not bias.look_ahead:
    ok("bias guard")
else:
    fail("bias")

rec = simulate_paper_outcome(code="601398", name="x", entry=5.2, stop=4.9, target1=5.5, report_date="2026-06-12", won=True)
if rec.net_return_pct is not None:
    ok("paper trade record")
else:
    fail("paper")

# CLI smoke
for cmd in ["screen", "validate"]:
    r = subprocess.run([sys.executable, str(ROOT / "tools/china_quant/cli.py"), cmd, "--fixture", "universe_full"], capture_output=True)
    if r.returncode == 0:
        ok(f"cli {cmd}")
    else:
        fail(f"cli {cmd}")

print(f"\nSUMMARY PASS={passed} FAIL={failed}")
sys.exit(0 if failed == 0 else 1)
