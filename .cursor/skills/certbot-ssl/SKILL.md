---
name: certbot-ssl
description: >-
  Generate Certbot/Let's Encrypt checklists and dry-run commands for HTTPS
  setup. Use when planning SSL certificates, renewal checks, or nginx/apache
  TLS config review. Never auto-run sudo, never modify production DNS or live
  certs without explicit user authorization.
disable-model-invocation: true
---

# Certbot SSL (Dry-Run Planner)

## Scope

This adapter provides planning and verification only. It does NOT execute certificate issuance.

## Workflow

1. Confirm domain, web server (nginx/apache/other), and environment (dev/staging/prod).
2. Output a checklist: DNS A/AAAA records, port 80/443, certbot package, webroot vs nginx plugin.
3. Provide dry-run commands only:

```bash
# Verify certbot installed
command -v certbot && certbot --version

# List existing certs (read-only)
certbot certificates

# Dry-run renewal (safe)
sudo certbot renew --dry-run
```

4. For new certs, output a **plan** with placeholders — user must approve before any `sudo certbot certonly` or `--nginx` run.

## Must not

- Run `sudo` without user authorization
- Modify `/etc/letsencrypt/`, nginx/apache live configs, or DNS
- Store or request API keys in skill files

## Rollback

Remove `.cursor/skills/certbot-ssl/` to uninstall this adapter.
