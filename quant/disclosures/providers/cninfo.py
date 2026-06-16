"""Official CNINFO disclosure provider (CSRC-designated platform)."""

from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any, Optional
from urllib.parse import urlparse

from quant.disclosures.models import normalize_cninfo_row
from quant.disclosures.protocol import (
    DisclosureCapabilities,
    DisclosureFetchResult,
    DisclosureProviderHealth,
    DisclosureStatus,
)
from quant.disclosures.raw_store import save_raw_response
from quant._config import CONFIG_DIR, load_config


class CNInfoOfficialProvider:
    name = "cninfo_official"
    source_class = "OFFICIAL_PERIODIC_AND_MATERIAL"
    _API = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
    _REFERER = "http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search"

    def _source_cfg(self) -> dict[str, Any]:
        cfg = load_config("disclosure_sources", defaults={"sources": []})
        for s in cfg.get("sources", []):
            if s.get("id") == "cninfo_his_announcement":
                return s
        return {"enabled": True, "maximum_requests_per_run": 30, "minimum_interval_seconds": 2}

    def _allowed(self, url: str) -> bool:
        cfg = self._source_cfg()
        if not cfg.get("enabled", False):
            return False
        host = urlparse(url).netloc
        return host.endswith("cninfo.com.cn")

    def health_check(self) -> DisclosureProviderHealth:
        ok = self._allowed(self._API)
        return DisclosureProviderHealth(
            provider_name=self.name,
            configured=ok,
            reachable=ok,
            status="READY" if ok else "NOT_CONFIGURED",
            checked_at=datetime.now().isoformat(timespec="seconds"),
            message="CNINFO official API allowlisted" if ok else "CNINFO not enabled in disclosure_sources.yaml",
        )

    def capabilities(self) -> DisclosureCapabilities:
        return DisclosureCapabilities(
            provider_name=self.name,
            exchanges=["SSE", "SZSE", "BSE", "ALL"],
            supports_symbol_filter=True,
            supports_category_filter=True,
            max_page_size=30,
        )

    def fetch_announcements(
        self,
        start_time: datetime,
        end_time: datetime,
        symbols: Optional[list[str]] = None,
        categories: Optional[list[str]] = None,
    ) -> DisclosureFetchResult:
        cfg = self._source_cfg()
        if not cfg.get("enabled", False):
            return self._result(start_time, end_time, DisclosureStatus.NOT_CONFIGURED, errors=["CNINFO disabled"])

        start_s = start_time.strftime("%Y-%m-%d")
        end_s = end_time.strftime("%Y-%m-%d")
        page_size = min(30, int(cfg.get("maximum_requests_per_run", 30)))
        body = (
            f"stock=&searchkey=&plate=&category=&trade=&seDate={start_s}~{end_s}"
            f"&pageNum=1&pageSize={page_size}&column=sse&tabName=fulltext&sortName=&sortType=&isHLtitle=true"
        ).encode("utf-8")

        req = urllib.request.Request(
            self._API,
            data=body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Referer": self._REFERER,
                "User-Agent": "netlify-demo-quant/1.0 (research; official-disclosure)",
            },
            method="POST",
        )
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=30, context=ssl.create_default_context()) as resp:
                raw_bytes = resp.read()
                status_code = resp.status
                headers = dict(resp.headers)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                return self._result(start_time, end_time, DisclosureStatus.RATE_LIMITED, errors=[f"HTTP 429"])
            if e.code in (401, 403):
                return self._result(start_time, end_time, DisclosureStatus.SOURCE_ACCESS_RESTRICTED, errors=[f"HTTP {e.code}"])
            return self._result(start_time, end_time, DisclosureStatus.NETWORK_UNAVAILABLE, errors=[str(e)])
        except Exception as e:
            return self._result(start_time, end_time, DisclosureStatus.NETWORK_UNAVAILABLE, errors=[str(e)])

        raw_path = save_raw_response(
            exchange="ALL",
            pub_time=end_s,
            source_url=self._API,
            content=raw_bytes,
            mime_type="application/json",
            disclosure_id=f"cninfo_query_{start_s}_{end_s}",
            headers=headers,
        )

        try:
            payload = json.loads(raw_bytes.decode("utf-8"))
        except json.JSONDecodeError as e:
            return self._result(
                start_time, end_time, DisclosureStatus.PARSE_ERROR,
                raw_paths=[raw_path["path"]], errors=[str(e)],
            )

        if not isinstance(payload, dict) or "announcements" not in payload:
            return self._result(
                start_time, end_time, DisclosureStatus.SCHEMA_ERROR,
                raw_paths=[raw_path["path"]], errors=["missing announcements key"],
            )

        anns = payload.get("announcements") or []
        rows = [normalize_cninfo_row(a, provider=self.name) for a in anns]
        if symbols:
            sym_set = {s.replace(".SH", "").replace(".SZ", "").replace(".BJ", "") for s in symbols}
            rows = [r for r in rows if r["stock_code"] in sym_set]
        for r in rows:
            r["raw_document_path"] = raw_path["path"]
            r["raw_hash_sha256"] = raw_path["hash"]

        st = DisclosureStatus.SUCCESS_WITH_ROWS if rows else DisclosureStatus.SUCCESS_ZERO_RESULTS
        return DisclosureFetchResult(
            provider_name=self.name,
            source_class=self.source_class,
            status=st,
            query_start=start_s,
            query_end=end_s,
            retrieval_time=datetime.now().isoformat(timespec="seconds"),
            row_count=len(rows),
            rows=rows,
            raw_artifact_paths=[raw_path["path"]],
            provider_timestamp=str(payload.get("totalAnnouncement", "")),
            warnings=[] if rows else ["official_query_returned_zero_announcements"],
        )

    def _result(
        self,
        start: datetime,
        end: datetime,
        status: DisclosureStatus,
        *,
        raw_paths: Optional[list[str]] = None,
        errors: Optional[list[str]] = None,
    ) -> DisclosureFetchResult:
        return DisclosureFetchResult(
            provider_name=self.name,
            source_class=self.source_class,
            status=status,
            query_start=start.strftime("%Y-%m-%d"),
            query_end=end.strftime("%Y-%m-%d"),
            retrieval_time=datetime.now().isoformat(timespec="seconds"),
            row_count=0,
            raw_artifact_paths=raw_paths or [],
            errors=errors or [],
        )
