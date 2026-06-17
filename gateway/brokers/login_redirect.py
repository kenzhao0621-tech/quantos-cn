"""Short-lived login redirect tokens — open official broker pages without API auth in new tab."""

from __future__ import annotations

import secrets
import time
from typing import Optional

_CACHE: dict[str, tuple[str, float]] = {}


def issue_login_redirect(url: str, *, ttl_sec: int = 300) -> str:
    token = secrets.token_urlsafe(18)
    _CACHE[token] = (url, time.time() + ttl_sec)
    _purge_expired()
    return token


def consume_login_redirect(token: str) -> Optional[str]:
    entry = _CACHE.pop(token, None)
    if not entry:
        return None
    url, exp = entry
    if time.time() > exp:
        return None
    return url


def _purge_expired() -> None:
    now = time.time()
    dead = [k for k, (_, exp) in _CACHE.items() if exp < now]
    for k in dead:
        _CACHE.pop(k, None)
