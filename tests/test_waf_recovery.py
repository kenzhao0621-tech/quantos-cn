from gateway.brokers.waf_recovery import extract_blocked_ip, is_waf_block, waf_recovery_for_broker


def test_waf_detect_nginx_forbidden():
    text = "<html>Nginx forbidden. request info: 223.64.208.62</html>"
    assert is_waf_block(text)
    assert extract_blocked_ip(text) == "223.64.208.62"


def test_eastmoney_fallback_urls():
    rec = waf_recovery_for_broker("eastmoney_manual")
    urls = [x["url"] for x in rec["fallback_urls"]]
    assert "https://www.18.cn/" in urls
    assert any("18.cn/soft" in u for u in urls)
