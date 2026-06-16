#!/usr/bin/env python3
"""Automated tests for web-content-safety-gate fixtures."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.web_content_safety.scanner import SafetyVerdict, scan_content

FIX = ROOT / "docs" / "test-fixtures" / "web-safety"
passed = failed = 0


def expect_quarantine(name: str, path: Path, content_type: str = "text") -> None:
    global passed, failed
    text = path.read_text(encoding="utf-8")
    r = scan_content(text, source=str(path.name), content_type=content_type)
    if r.quarantined:
        passed += 1
        print(f"PASS {name} -> {r.verdict.value}")
    else:
        failed += 1
        print(f"FAIL {name} expected QUARANTINE/BLOCK got {r.verdict.value}")


def expect_pass(name: str, path: Path, content_type: str = "text") -> None:
    global passed, failed
    text = path.read_text(encoding="utf-8")
    r = scan_content(text, source=str(path.name), content_type=content_type)
    if r.verdict == SafetyVerdict.PASS:
        passed += 1
        print(f"PASS {name}")
    else:
        failed += 1
        print(f"FAIL {name} expected PASS got {r.verdict.value} {r.issues}")


# Malicious fixtures — must quarantine
for fname in [
    "direct_prompt_injection.txt",
    "indirect_prompt_injection.md",
    "html_hidden_text.html",
    "markdown_instructions.md",
    "malicious_json.json",
    "fake_admin_message.txt",
    "fake_tool_output.txt",
    "encoded_credential_request.txt",
    "malicious_readme.md",
    "research_paper_embedded.txt",
    "ignore_previous.html",
    "cursor_rules_override.txt",
    "shell_command_suggestion.txt",
    "env_var_request.txt",
    "disable_security.txt",
    "install_arbitrary.txt",
    "exfiltrate_source.txt",
]:
    p = FIX / fname
    if p.exists():
        ct = "html" if fname.endswith(".html") else "json" if fname.endswith(".json") else "text"
        expect_quarantine(fname, p, ct)

# Benign fixture
expect_pass("benign_financial_fact", FIX / "benign_financial_fact.txt")

print(f"\nSUMMARY PASS={passed} FAIL={failed}")
sys.exit(0 if failed == 0 else 1)
