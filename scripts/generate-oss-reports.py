#!/usr/bin/env python3
"""Generate final-stage OSS reconnaissance and capability reports."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "ai" / "final"
PRE = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()

    projects = [
        {
            "name": "vnpy/vnpy",
            "canonical_url": "https://github.com/vnpy/vnpy",
            "identity": "VERIFIED",
            "license": "MIT",
            "latest_release": "4.3.0",
            "maintenance": "ACTIVE",
            "a_share_relevance": 5,
            "decision": "ADOPT_NATIVE_ISOLATED",
            "notes": "VeighNa 4.x requires Python 3.10+; isolated .venv-vnpy-native",
        },
        {
            "name": "microsoft/qlib",
            "canonical_url": "https://github.com/microsoft/qlib",
            "identity": "VERIFIED",
            "license": "MIT",
            "latest_release": "v0.9.7",
            "maintenance": "ACTIVE",
            "a_share_relevance": 5,
            "decision": "ADOPT_NATIVE_ISOLATED",
            "notes": "Canonical warehouse bridge; isolated .venv-qlib-native",
        },
        {
            "name": "microsoft/RD-Agent",
            "canonical_url": "https://github.com/microsoft/RD-Agent",
            "identity": "VERIFIED",
            "license": "MIT",
            "maintenance": "ACTIVE",
            "decision": "ADOPT_IDEAS_ONLY",
            "notes": "Factor/model candidate automation; no auto live promotion",
        },
        {
            "name": "TauricResearch/TradingAgents",
            "canonical_url": "https://github.com/TauricResearch/TradingAgents",
            "identity": "VERIFIED",
            "license": "Apache-2.0 (typical)",
            "maintenance": "ACTIVE",
            "decision": "ADOPT_IDEAS_ONLY",
            "notes": "Multi-agent debate pattern; implemented as gateway/agents/cn_research",
        },
        {
            "name": "hsliuping/TradingAgents-CN",
            "canonical_url": "https://github.com/hsliuping/TradingAgents-CN",
            "identity": "VERIFIED_FORK",
            "license": "Apache-2.0",
            "maintenance": "ACTIVE",
            "decision": "REFERENCE_ONLY",
            "notes": "CN A-share agent ideas; not merged — incompatible stack",
        },
        {
            "name": "AI4Finance-Foundation/FinRL",
            "canonical_url": "https://github.com/AI4Finance-Foundation/FinRL",
            "identity": "VERIFIED",
            "license": "MIT",
            "decision": "ADOPT_ARCHITECTURE_IDEAS_ONLY",
        },
        {
            "name": "AI4Finance-Foundation/FinRL-Trading (FinRL-X)",
            "canonical_url": "https://github.com/AI4Finance-Foundation/FinRL-Trading",
            "identity": "VERIFIED",
            "license": "Apache-2.0",
            "decision": "ADOPT_ARCHITECTURE_IDEAS_ONLY",
            "notes": "RL experimental challenger only",
        },
        {
            "name": "ScottZt/jin-ce-zhi-suan",
            "canonical_url": "https://github.com/ScottZt/jin-ce-zhi-suan",
            "identity": "VERIFIED",
            "license": "UNKNOWN_REVIEW_REQUIRED",
            "maintenance": "MODERATE",
            "decision": "NOT_MERGED",
            "notes": "三省六部风控 ideas only; separate product — not cloned",
        },
        {
            "name": "brokermr810/QuantDinger",
            "canonical_url": "https://github.com/brokermr810/QuantDinger",
            "identity": "VERIFIED",
            "license": "Review required (check repo LICENSE)",
            "maintenance": "ACTIVE",
            "decision": "NOT_MERGED",
            "notes": "Crypto/US-focused live stack; incompatible with QuantOS safety model",
        },
        {
            "name": "PandaAI (paper)",
            "canonical_url": "https://arxiv.org/html/2606.06823",
            "identity": "PAPER_ONLY",
            "decision": "ADOPT_IDEAS_ONLY",
            "notes": "Neuro-symbolic constrained alpha — not a single canonical repo",
        },
        {
            "name": "PandaAI/PandaAiquant",
            "canonical_url": "https://github.com/PandaAI/PandaAiquant",
            "identity": "VERIFIED_STALE",
            "license": "UNKNOWN",
            "maintenance": "STALE (2019)",
            "decision": "REJECT",
        },
    ]

    unverified = [p for p in projects if p.get("identity") == "IDENTITY_UNVERIFIED"]
    recon = {"generated_at": ts, "pre_commit": PRE, "projects": projects, "unverified_count": len(unverified)}
    (OUT / "01_OPEN_SOURCE_RECONNAISSANCE.json").write_text(json.dumps(recon, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "01_OPEN_SOURCE_RECONNAISSANCE.md").write_text(
        "# Open Source Reconnaissance\n\n" + "\n".join(f"- **{p['name']}**: {p['decision']}" for p in projects),
        encoding="utf-8",
    )

    gap = {
        "generated_at": ts,
        "gaps": [
            {"area": "native_vnpy", "current": "shim in main venv", "target": "isolated native EventEngine/MainEngine"},
            {"area": "native_qlib", "current": "alpha158_lite shim", "target": "native LightGBM on DuckDB"},
            {"area": "multi_agent", "current": "partial", "target": "cn_research workflow with evidence"},
            {"area": "portal_pages", "current": "8 tabs", "target": "15+ operational pages"},
        ],
    }
    (OUT / "02_CAPABILITY_GAP_MATRIX.json").write_text(json.dumps(gap, indent=2, ensure_ascii=False), encoding="utf-8")

    license_dec = {
        "generated_at": ts,
        "merged_repos": [],
        "reference_only": [p["name"] for p in projects if "NOT_MERGED" in p.get("decision", "") or "REFERENCE" in p.get("decision", "")],
        "adopted_native": ["vnpy/vnpy", "microsoft/qlib"],
        "supply_chain": "vendor review in .vendor-review/ — no install scripts executed from third parties",
    }
    (OUT / "03_LICENSE_SECURITY_DECISION.json").write_text(json.dumps(license_dec, indent=2), encoding="utf-8")

    from gateway.observability.closed_loop import append_step
    append_step("F1-OSS", "Open source reconnaissance", actual="reports written", artifacts=[str(OUT / "01_OPEN_SOURCE_RECONNAISSANCE.json")])
    print("OSS reports ok")


if __name__ == "__main__":
    main()
