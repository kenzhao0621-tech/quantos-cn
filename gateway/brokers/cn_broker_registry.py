"""China A-share broker ecosystem registry — official portals, launch targets, quant paths."""

from __future__ import annotations

from typing import Any

# broker_id → profile used in broker_config.json active_broker
CN_BROKER_ECOSYSTEM: dict[str, dict[str, Any]] = {
    "eastmoney_manual": {
        "label": "东方财富证券",
        "vendor": "东方财富",
        "handoff": "browser_launch",
        "ecosystem": ["东方财富 App", "掘金 EMT API", "jywg 网页交易"],
        "urls": {
            "portal": "https://www.18.cn/",
            "trade_login": "https://www.18.cn/",
            "trade_login_alt": "https://jywg.eastmoneysec.com/",
            "trade_login_mobile": "https://wap.eastmoney.com/",
            "software": "https://www.18.cn/soft/",
            "quant_api": "https://emt.18.cn/",
            "open_account": "https://kh.eastmoney.com/",
        },
        "fallback_urls": [
            {"label": "官网首页（推荐，不易 403）", "url": "https://www.18.cn/"},
            {"label": "东方财富 App 下载", "url": "https://www.18.cn/soft/"},
            {"label": "网页交易 jywg（易被 WAF 拦截）", "url": "https://jywg.eastmoneysec.com/"},
            {"label": "手机版", "url": "https://wap.eastmoney.com/"},
        ],
        "app_scheme_stock": "dfcft://stock?code={code}&market={market_id}",
        "quote_template": "https://quote.eastmoney.com/{market}{code}.html",
        "watchlist_hint": "打开行情页 → 点击「加自选」",
        "order_hint": "登录 jywg 交易页 → 搜索代码 → 买入确认",
    },
    "huatai_zhangle": {
        "label": "华泰证券 · 涨乐财富通",
        "vendor": "华泰证券",
        "handoff": "browser_launch",
        "ecosystem": ["涨乐财富通 App", "涨乐财富通 PC", "华泰网厅", "PTrade 量化"],
        "urls": {
            "portal": "https://www.htsc.com.cn/",
            "trade_login": "https://m.zhangle.com/",
            "trade_login_alt": "https://www.htsc.com.cn/portal/main/home/index.html",
            "software": "https://www.htsc.com.cn/browser/mobile/mobileSecurities/SoftwareDownload.jsp",
            "quant_api": "https://www.htsc.com.cn/",
            "open_account": "https://www.htsc.com.cn/",
        },
        "quote_template": "https://stockpage.10jqka.com.cn/{code}/",
        "watchlist_hint": "涨乐 App → 自选股 → 添加；或网厅扫码登录后操作",
        "order_hint": "网厅客户号登录（需安全控件）或 App 内下单",
        "notes": "网页交易需 IE/360 兼容模式；推荐 App 扫码登录网厅",
    },
    "flush_tonghuashun": {
        "label": "同花顺 · 券商交易入口",
        "vendor": "同花顺",
        "handoff": "browser_launch",
        "login_type": "app_via_ths",
        "ecosystem": ["同花顺 App", "iFinD", "接入多家券商交易"],
        "external_steps": [
            "下载并安装同花顺 App（下方「下载 App」）",
            "在 App 内添加你已开户的券商账户",
            "用本系统选股后，在同花顺 App 内搜索代码并下单",
        ],
        "urls": {
            "portal": "https://www.10jqka.com.cn/",
            "trade_login": "https://upass.10jqka.com.cn/login",
            "trade_login_alt": "https://www.10jqka.com.cn/download/index/download/id/1/",
            "software": "https://www.10jqka.com.cn/download/",
            "quant_api": "https://www.10jqka.com.cn/",
            "open_account": "https://www.10jqka.com.cn/",
        },
        "quote_template": "https://stockpage.10jqka.com.cn/{code}/",
        "watchlist_hint": "同花顺 App → 自选股 → 添加",
        "order_hint": "同花顺为聚合入口：须先在 App 绑定券商账户，再在 App 内确认下单",
    },
    "gtja_junhong": {
        "label": "国泰君安 · 君弘",
        "vendor": "国泰君安",
        "handoff": "browser_launch",
        "ecosystem": ["君弘 App", "富易 PC", "道合机构"],
        "urls": {
            "portal": "https://www.gtja.com/",
            "trade_login": "https://dl.app.gtja.com/public/m/index.html",
            "software": "http://fy.gtja.com/",
            "quant_api": "https://www.gtja.com/",
            "open_account": "https://www.gtja.com/",
        },
        "quote_template": "https://stockpage.10jqka.com.cn/{code}/",
        "watchlist_hint": "君弘 App → 自选 → 添加股票",
        "order_hint": "君弘 App 或富易客户端登录后交易",
    },
    "cms_zhaoshang": {
        "label": "招商证券 · 智远一户通",
        "vendor": "招商证券",
        "handoff": "browser_launch",
        "ecosystem": ["智远一户通 App", "招商证券网厅"],
        "urls": {
            "portal": "https://www.newone.com.cn/",
            "trade_login": "https://www.newone.com.cn/main/onlinebusiness/tradingsoftware/index.html",
            "software": "https://www.newone.com.cn/main/onlinebusiness/tradingsoftware/index.html",
            "open_account": "https://www.newone.com.cn/",
        },
        "quote_template": "https://stockpage.10jqka.com.cn/{code}/",
        "watchlist_hint": "智远一户通 → 自选管理",
        "order_hint": "官方 App 登录后交易",
    },
    "citic_xintou": {
        "label": "中信证券 · 信e投",
        "vendor": "中信证券",
        "handoff": "browser_launch",
        "ecosystem": ["信e投 App", "中信证券官网"],
        "urls": {
            "portal": "https://www.citics.com/",
            "trade_login": "https://www.citics.com/newsite/online/index.html",
            "software": "https://www.citics.com/newsite/softwareDownload/index.html",
            "open_account": "https://www.citics.com/",
        },
        "quote_template": "https://stockpage.10jqka.com.cn/{code}/",
        "watchlist_hint": "信e投 → 自选股",
        "order_hint": "信e投 App 登录交易",
    },
    "gf_yitajin": {
        "label": "广发证券 · 易淘金",
        "vendor": "广发证券",
        "handoff": "browser_launch",
        "ecosystem": ["易淘金 App", "广发证券网厅"],
        "urls": {
            "portal": "https://www.gf.com.cn/",
            "trade_login": "https://store.gf.com.cn/",
            "software": "https://www.gf.com.cn/web/software/index.html",
            "open_account": "https://www.gf.com.cn/",
        },
        "quote_template": "https://stockpage.10jqka.com.cn/{code}/",
        "watchlist_hint": "易淘金 → 自选",
        "order_hint": "易淘金 App 登录后下单",
    },
    "galaxy_chinastock": {
        "label": "中国银河证券",
        "vendor": "银河证券",
        "handoff": "browser_launch",
        "ecosystem": ["中国银河证券 App", "银河网厅"],
        "urls": {
            "portal": "https://www.chinastock.com.cn/",
            "trade_login": "https://www.chinastock.com.cn/",
            "software": "https://www.chinastock.com.cn/",
            "open_account": "https://www.chinastock.com.cn/",
        },
        "quote_template": "https://stockpage.10jqka.com.cn/{code}/",
        "watchlist_hint": "银河 App → 自选股",
        "order_hint": "官方 App 登录交易",
    },
    "pingan_securities": {
        "label": "平安证券",
        "vendor": "平安证券",
        "handoff": "browser_launch",
        "ecosystem": ["平安证券 App", "平安证券官网"],
        "urls": {
            "portal": "https://stock.pingan.com/",
            "trade_login": "https://stock.pingan.com/",
            "software": "https://stock.pingan.com/",
            "open_account": "https://stock.pingan.com/",
        },
        "quote_template": "https://stockpage.10jqka.com.cn/{code}/",
        "watchlist_hint": "平安证券 App → 自选",
        "order_hint": "App 登录后交易",
    },
    "qmt_local": {
        "label": "MiniQMT / xtquant · 多券商量化",
        "vendor": "迅投 QMT",
        "handoff": "xtquant_api",
        "ecosystem": ["MiniQMT", "xtquant", "国金/华泰/中信等券商 QMT"],
        "urls": {
            "portal": "https://www.myquant.cn/",
            "trade_login": "https://www.myquant.cn/",
            "software": "https://www.myquant.cn/",
            "quant_api": "http://docs.thinktrader.net/vip/pages/ee0e9b/",
        },
        "notes": "MiniQMT 仅支持 Windows；macOS 需虚拟机运行客户端",
    },
    "xtp_readonly": {
        "label": "中泰 XTP · 只读/仿真",
        "vendor": "中泰证券",
        "handoff": "xtp_api",
        "ecosystem": ["XTP API"],
        "urls": {
            "portal": "https://xtp.zts.com.cn/",
            "trade_login": "https://xtp.zts.com.cn/",
            "software": "https://xtp.zts.com.cn/",
        },
    },
    "paper_only": {
        "label": "仅 Paper/Shadow 模拟",
        "vendor": "QuantOS",
        "handoff": "simulation",
        "ecosystem": ["Paper", "Shadow"],
        "urls": {"portal": ""},
    },
    "mac_sidecar": {
        "label": "Mac · 远程交易 Sidecar（推荐实盘）",
        "vendor": "QuantOS",
        "handoff": "remote_sidecar",
        "ecosystem": ["Windows VM MiniQMT", "Linux XTP", "HTTP 自动下单"],
        "urls": {
            "portal": "https://www.myquant.cn/",
            "software": "https://www.myquant.cn/",
        },
        "notes": "Mac 本机 Gateway + Windows 虚拟机 Sidecar，经 HTTP 提交真实委托",
        "order_hint": "门控通过后自动经 Sidecar 发单至虚拟机内 MiniQMT",
    },
}


BROWSER_BROKER_IDS = frozenset(
    k for k, v in CN_BROKER_ECOSYSTEM.items() if v.get("handoff") == "browser_launch"
)


def list_broker_profiles() -> dict[str, dict[str, Any]]:
    """Shape for connection_manager BROKER_PROFILES."""
    out: dict[str, dict[str, Any]] = {}
    for bid, spec in CN_BROKER_ECOSYSTEM.items():
        urls = spec.get("urls") or {}
        out[bid] = {
            "label": spec["label"],
            "handoff": spec.get("handoff", "browser_launch"),
            "portal_url": urls.get("trade_login") or urls.get("portal", ""),
            "vendor": spec.get("vendor", ""),
            "ecosystem": spec.get("ecosystem", []),
            "requires": [] if bid not in ("xtp_readonly",) else ["xtp_host", "xtp_port"],
            "notes": spec.get("notes", ""),
        }
    return out


def portal_links() -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    seen: set[str] = set()
    for spec in CN_BROKER_ECOSYSTEM.values():
        urls = spec.get("urls") or {}
        for key, title in (
            ("trade_login", "网页交易"),
            ("software", "客户端下载"),
            ("quant_api", "量化 API"),
        ):
            url = urls.get(key)
            if not url or url in seen:
                continue
            seen.add(url)
            links.append({
                "name": f"{spec['vendor']} · {title}",
                "type": title,
                "url": url,
                "note": spec.get("order_hint") or spec.get("notes") or spec["label"],
            })
    return links
