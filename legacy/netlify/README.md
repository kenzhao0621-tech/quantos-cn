# Legacy Netlify static demo

This folder contains the **original Netlify plugin demo** (static site + `status` function). It is **not** the QuantOS CN quant portal.

## QuantOS CN (main product)

Run the China A-share quant platform locally:

```bash
make bootstrap
make app
# → http://127.0.0.1:8787/portal
```

## Run this legacy demo (optional)

```bash
cd legacy/netlify
npx netlify dev
```

Or from repo root if you restore `netlify.toml` symlink.
