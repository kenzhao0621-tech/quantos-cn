---
name: dependency-guard
description: >-
  Pre-install npm/pip dependency security scan (typosquatting, postinstall scripts,
  CVE checks). FALLBACK markdown procedures; PRIMARY is ci-fixer + npm/pip audit.
  Use before npm install, pip install, or adding MCP/plugin dependencies. Archived
  upstream — vendored copy pinned. Do NOT auto-install packages after scan failure.
license: MIT
metadata:
  upstream: aptratcn/skill-dependency-guard
  upstream_commit: 944f7c94bf9da83e206709edd137b1ee8886cb5b
  archived: true
---

# Dependency Guard 🛡️

**Pre-install dependency security scanner for AI agents.**

Stop supply chain attacks before they reach your agent. Scan npm/pip packages for vulnerabilities, typosquatting, suspicious authors, and known exploits BEFORE you install.

## When This Skill Triggers

- Agent is about to `npm install` or `pip install` a package
- User asks "is this package safe?", "scan this dependency", "check for vulnerabilities"
- Adding MCP servers or agent plugins that pull in dependencies
- CI/CD pipeline needs dependency vetting
- Keywords: dependency audit, supply chain, npm audit, pip audit, package safety, typosquatting

## The Problem

Supply chain attacks are the #1 growing threat for AI agents:

- **Bitwarden CLI was compromised** via npm typosquatting (April 2026) — attackers replaced a trusted CLI with a malicious version
- **86% of repos** have at least one known vulnerability in dependencies
- **Average time to detect** a compromised package: 209 days
- **AI agents are prime targets** — they install packages automatically, run with high privileges, and handle sensitive data

Agents install MCP servers, plugins, and tools without checking if the package is legitimate. One `npm install` can compromise your entire system.

## Quick Assessment (30 seconds)

Before installing ANY package, run these checks:

```bash
# NPM packages
npm view <package> version    # Check latest version exists
npm view <package> author     # Verify author
npm view <package> created    # New package = suspicious
npm audit --production        # Check known CVEs

# Python packages
pip index versions <package>  # Check PyPI listing
pip-audit                    # Scan for CVEs
```

## Full Scan Procedure

### Step 1: Package Metadata Check

```bash
# NPM - Check for red flags
npm view <package> --json | jq '{
  name: .name,
  version: .version,
  author: .author,
  created: .time.created,
  modified: .time.modified,
  maintainers: (.maintainers | length),
  dependencies: (.dependencies | keys | length),
  homepage: .homepage,
  repository: .repository.url
}'
```

**Red flags in metadata:**
- Created < 30 days ago (new, untested)
- Only 1 maintainer (single point of failure)
- Name is a typosquat of a popular package (e.g., `lodassh` vs `lodash`)
- No repository URL or homepage
- Sudden version spike (1.0.0 → 99.0.0 in days)

### Step 2: Typosquat Detection

Common typosquatting patterns:
```
Popular package  →  Fake package
─────────────────────────────────
lodash           →  lodassh, lodash-utils
express          →  expres, expressjs-core
react            →  react-native-core
openai           →  openaai, openai-sdk
@anthropic-ai/sdk → @anthropic/sdk
```

Check algorithm:
1. Extract package name
2. Compare against top-1000 npm/PyPI packages
3. Flag if edit distance ≤ 2 from a popular package
4. Check if name swaps common suffixes (-cli, -sdk, -core, -utils)

### Step 3: Dependency Graph Analysis

```bash
# Check what the package pulls in
npm ls <package> --all          # Full dependency tree
npm dedupe --dry-run            # Check for conflicts

# Python
pip-compile --dry-run requirements.txt
pip-audit -r requirements.txt   # CVE check
```

**Red flags in dependencies:**
- Deep dependency chains (> 5 levels)
- Unexpected network libraries (axios, node-fetch in a pure-logic package)
- File system access packages in a data-only package
- eval() or vm2 in transitive dependencies
- Post-install scripts

### Step 4: Post-Install Script Check

```bash
# NPM - Check for install hooks
npm view <package> scripts --json
# Look for: preinstall, install, postinstall
# These run arbitrary code on your machine

# Check package.json in the tarball
npm pack <package> --dry-run 2>&1 | grep -E "(preinstall|postinstall|install)"
```

**NEVER install packages with postinstall scripts from untrusted sources.** This is how Bitwarden CLI was compromised — the malicious package ran code during installation.

### Step 5: Code Inspection (for high-risk packages)

```bash
# Download without installing
npm pack <package>
tar -xzf <package>-*.tgz
cd package

# Scan for dangerous patterns
grep -rn "eval(" .
grep -rn "Function(" .
grep -rn "child_process" .
grep -rn "require('net')" .
grep -rn "require('http')" .
grep -rn "process.env" .
grep -rn "atob(" .
grep -rn "fetch(" .
grep -rn "XMLHttpRequest" .
grep -rn "Buffer\.from.*toString" .

# Check for obfuscation
find . -name "*.js" -exec file {} \; | grep "minified\|obfuscated"
```

## Risk Scoring

| Factor | Weight | Score |
|--------|--------|-------|
| Known CVEs | 30 | -30 per critical CVE |
| Post-install scripts | 20 | -20 if present |
| Typosquat similarity | 20 | -20 if match |
| Package age < 30 days | 15 | -15 if new |
| Single maintainer | 10 | -10 if only 1 |
| Suspicious dependencies | 5 | -5 per flagged dep |

**Total ≥ 0**: ✅ Safe to install
**Total -1 to -30**: ⚠️ Install with caution, review code
**Total < -30**: 🚫 Do not install

## CI/CD Integration

### GitHub Actions

```yaml
name: Dependency Guard
on: [pull_request]
jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: |
          # Check for new dependencies in package.json
          git diff origin/main -- package.json | grep "+    " | while read line; do
            pkg=$(echo "$line" | sed 's/.*"\([^"]*\)".*/\1/')
            echo "Scanning new dependency: $pkg"
            npm view "$pkg" scripts --json
            npm view "$pkg" --json | jq '{name, author, created: .time.created}'
          done
      - run: npm audit --production
      - run: npx better-npm-audit audit --level moderate
```

### Pre-install Hook

Add to your agent's startup script:

```bash
# .bashrc or agent config
npm_guard() {
  for pkg in "$@"; do
    # Block packages with postinstall scripts
    if npm view "$pkg" scripts 2>/dev/null | grep -q "postinstall"; then
      echo "🚫 Blocked: $pkg has postinstall script"
      return 1
    fi
    # Block typosquats
    if npm view "$pkg" --json 2>/dev/null | jq -r '.time.created' | xargs -I{} days_since {} | grep -q "^[0-2][0-9]$"; then
      echo "⚠️  Warning: $pkg is less than 30 days old"
    fi
  done
  npm install "$@"
}
```

## Known Attack Patterns

### 1. Typosquatting
Publish `lodassh` hoping you type it instead of `lodash`. The malicious package may have identical API but phone home.

### 2. Dependency Confusion
Publish `my-company-utils` to public npm with version 99.0.0. If your agent resolves packages without scoped registries, it pulls the public one instead of your private one.

### 3. Install-Time Execution
`postinstall` scripts run with full system access. The Bitwarden CLI attack injected a credential stealer that ran during `npm install`.

### 4. Star/Deloading
Attacker creates a legitimate-looking package, builds trust over months, then pushes a malicious update. Always pin versions.

### 5. Transitive Attack
Compromise a popular sub-dependency. Your agent doesn't directly install it, but it gets pulled in via your real dependencies.

## Emergency Response

If you suspect a compromised package:

```
1. UNINSTALL  → npm uninstall <package> / pip uninstall <package>
2. ROTATE     → Change ALL credentials that were accessible during install
3. AUDIT      → Check access logs, network logs for exfiltration
4. REPORT     → File security advisory on npm/PyPI
5. SCAN       → Run full dependency audit: npm audit / pip-audit
6. PIN        → Lock all dependency versions: npm shrinkwrap / pip freeze
```

## Related Skills

- [skill-mcp-security-audit](https://github.com/aptratcn/skill-mcp-security-audit) - Audit MCP server code
- [skill-git-secret-sweep](https://github.com/aptratcn/skill-git-secret-sweep) - Scan for leaked secrets
