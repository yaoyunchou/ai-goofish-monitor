import importlib

import src.scraper as scraper_module


def _reload_scraper():
    return importlib.reload(scraper_module)


def test_build_extra_headers_blocks_sec_fetch_and_referer():
    scraper = _reload_scraper()
    headers = scraper._build_extra_headers(
        {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.goofish.com/personal",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Accept-Language": "zh-CN",
        }
    )
    assert "Referer" not in headers
    assert "Sec-Fetch-Site" not in headers
    assert headers.get("Accept-Language") == "zh-CN"


def test_snapshot_to_playwright_storage_includes_local_storage():
    scraper = _reload_scraper()
    snapshot = {
        "pageUrl": "https://www.goofish.com/personal?userId=1",
        "cookies": [{"name": "t", "value": "abc", "domain": ".goofish.com", "path": "/"}],
        "storage": {
            "local": {"foo": "bar"},
            "session": {"sid": "xyz"},
        },
    }
    state = scraper._snapshot_to_playwright_storage(snapshot)
    assert len(state["cookies"]) == 1
    assert state["origins"][0]["origin"] == "https://www.goofish.com"
    assert state["origins"][0]["localStorage"] == [{"name": "foo", "value": "bar"}]
    assert state["origins"][0]["sessionStorage"] == [{"name": "sid", "value": "xyz"}]
