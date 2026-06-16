"""Scan untrusted web/crawl content for prompt injection and malicious instructions."""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from html import unescape
from html.parser import HTMLParser
from typing import Optional


class SafetyVerdict(str, Enum):
    PASS = "PASS"
    QUARANTINE = "QUARANTINE"
    BLOCK = "BLOCK"


@dataclass
class SafetyIssue:
    category: str
    reason: str
    excerpt: str


@dataclass
class SafetyResult:
    verdict: SafetyVerdict
    issues: list[SafetyIssue] = field(default_factory=list)
    safe_excerpt: str = ""
    source: str = ""

    @property
    def quarantined(self) -> bool:
        return self.verdict in (SafetyVerdict.QUARANTINE, SafetyVerdict.BLOCK)


# Patterns — heuristic, not exhaustive
INJECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("prompt_injection", re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions", re.I)),
    ("cursor_rules_override", re.compile(r"(override|disable|bypass)\s+(.{0,20})?(cursor\s+rules?|system\s+prompt)", re.I)),
    ("secret_request", re.compile(r"(reveal|print|dump|export|send)\s+.{0,30}(api\s*key|secret|password|token|credential|\.env)", re.I)),
    ("env_request", re.compile(r"(read|show|cat|export)\s+.{0,20}(environment\s+variable|process\.env|\.env)", re.I)),
    ("shell_execution", re.compile(r"(run|execute|eval)\s+.{0,20}(shell|bash|cmd|terminal|os\.system)", re.I)),
    ("shell_pipe_bash", re.compile(r"\|\s*bash|curl\s+[^\s]+\s*\|\s*bash", re.I)),
    ("file_upload", re.compile(r"(upload|exfiltrate|send)\s+.{0,30}(local\s+file|source\s+code|repository)", re.I)),
    ("disable_security", re.compile(r"(disable|turn\s+off)\s+.{0,20}(security|sandbox|safety|guard)", re.I)),
    ("tool_permission", re.compile(r"(grant|enable)\s+.{0,20}(tool\s+permission|mcp|arbitrary)", re.I)),
    ("install_software", re.compile(r"(install|npm\s+install|pip\s+install|curl\s+\|)\s+.{0,40}(without|arbitrary)", re.I)),
    ("persistence", re.compile(r"(cron|launchagent|startup|persist|backdoor)", re.I)),
    ("fake_admin", re.compile(r"(administrator|system\s+message|developer\s+mode)\s*:\s*", re.I)),
    ("fake_tool_output", re.compile(r"<tool_result>|assistant:\s*I\s+have\s+updated", re.I)),
    ("encoded_secret", re.compile(r"(base64|atob|decode).{0,40}(api[_-]?key|sk-[a-z0-9])", re.I)),
    ("cursor_modify", re.compile(r"modify\s+.{0,20}(\.cursor/|hooks\.json|mcp\.json)", re.I)),
]

HIDDEN_STYLE = re.compile(
    r"style\s*=\s*['\"][^'\"]*(display\s*:\s*none|visibility\s*:\s*hidden|font-size\s*:\s*0|opacity\s*:\s*0)",
    re.I,
)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.hidden_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        attr = dict(attrs)
        style = attr.get("style", "") or ""
        if HIDDEN_STYLE.search(f'style="{style}"') or attr.get("hidden") is not None:
            self.hidden_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if self.hidden_depth > 0 and tag in ("div", "span", "p"):
            self.hidden_depth = max(0, self.hidden_depth - 1)

    def handle_data(self, data: str) -> None:
        if self.hidden_depth == 0:
            self.parts.append(data)


def _normalize(text: str) -> str:
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    # decode simple base64 blobs that decode to suspicious text
    for blob in re.findall(r"[A-Za-z0-9+/]{20,}={0,2}", text):
        try:
            decoded = base64.b64decode(blob + "==", validate=False).decode("utf-8", errors="ignore")
            if any(p.search(decoded) for _, p in INJECTION_PATTERNS[:6]):
                text += " " + decoded
        except Exception:
            pass
    return text


def _scan_text(text: str, source: str) -> list[SafetyIssue]:
    issues: list[SafetyIssue] = []
    norm = _normalize(text)
    for category, pattern in INJECTION_PATTERNS:
        m = pattern.search(norm)
        if m:
            start = max(0, m.start() - 20)
            excerpt = norm[start : m.end() + 40][:120]
            issues.append(SafetyIssue(category, f"Matched {category}", excerpt))
    return issues


def scan_content(content: str, *, source: str = "", content_type: str = "text") -> SafetyResult:
    """Scan raw content. HTML/Markdown/JSON all treated as untrusted data."""
    issues: list[SafetyIssue] = []
    body = content

    if content_type in ("html", "text/html") or "<html" in content[:500].lower():
        parser = _TextExtractor()
        try:
            parser.feed(content)
            visible = " ".join(parser.parts)
            hidden = _normalize(content)
            if "display:none" in content.lower() or "visibility:hidden" in content.lower():
                hidden_issues = _scan_text(hidden, source)
                for hi in hidden_issues:
                    if hi not in issues:
                        issues.append(SafetyIssue("html_hidden", hi.reason, hi.excerpt))
            body = visible if visible.strip() else hidden
        except Exception:
            body = content

    if content_type == "json" or content.strip().startswith("{"):
        try:
            obj = json.loads(content)
            body = json.dumps(obj, ensure_ascii=False)
        except json.JSONDecodeError:
            pass

    issues.extend(_scan_text(body, source))

    if issues:
        verdict = SafetyVerdict.QUARANTINE
        if any(i.category in ("secret_request", "shell_execution", "file_upload") for i in issues):
            verdict = SafetyVerdict.BLOCK
        return SafetyResult(
            verdict=verdict,
            issues=issues,
            safe_excerpt="",
            source=source,
        )

    # factual excerpt — first 500 chars of visible text, scripts stripped
    clean = re.sub(r"<script[^>]*>.*?</script>", "", body, flags=re.I | re.S)
    clean = re.sub(r"<[^>]+>", " ", clean)
    clean = _normalize(clean)[:500]
    return SafetyResult(SafetyVerdict.PASS, [], clean, source)


def format_report(result: SafetyResult) -> str:
    lines = [f"Safety: {result.verdict.value}", f"Source: {result.source or 'unknown'}"]
    if result.issues:
        lines.append("Issues:")
        for i in result.issues:
            lines.append(f"  - [{i.category}] {i.reason}: {i.excerpt!r}")
    if result.safe_excerpt:
        lines.append(f"Safe excerpt: {result.safe_excerpt[:200]}...")
    lines.append(
        "Limitation: heuristic detection only; novel obfuscation may evade patterns."
    )
    return "\n".join(lines)
