"""
闲鱼 PC 端 MTOP H5 调用（与浏览器详情页 POST 一致）。

签名规则：md5(f"{token}&{t}&{appKey}&{data}")，token 为 Cookie _m_h5_tk 下划线前一段。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import requests

from src.config import PROXY_URL
from src.utils import log_time

GOOFISH_MTOP_APP_KEY = "34839810"
GOOFISH_MTOP_JSV = "2.7.2"
IDLE_PC_DETAIL_API = "mtop.taobao.idle.pc.detail"
IDLE_PC_DETAIL_PATH = f"/h5/{IDLE_PC_DETAIL_API}/1.0/"
GOOFISH_H5API_ORIGIN = "https://h5api.m.goofish.com"

DEFAULT_HEADERS = {
    "accept": "application/json",
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://www.goofish.com",
    "referer": "https://www.goofish.com/",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
}


class IdleMtopError(RuntimeError):
    pass


def extract_item_id_from_link(link: str) -> Optional[str]:
    text = str(link or "").strip()
    if not text:
        return None
    patterns = (
        r"item\?[^#]*\bid=(\d+)",
        r"itemId=(\d+)",
        r"awesome_detail[^#]*\bid=(\d+)",
        r"/item/(\d+)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def load_state_cookies(state_file: str) -> List[dict]:
    """从 DB 或文件加载登录态 cookies。"""
    from src.services.account_state_store import get_account_state
    state = get_account_state(state_file)
    if state is None:
        raise FileNotFoundError(f"登录状态不存在: {state_file}")
    if not isinstance(state, dict):
        raise ValueError("state 格式无效，需要 Playwright storage_state JSON。")
    cookies = state.get("cookies")
    if not isinstance(cookies, list):
        raise ValueError("state 缺少 cookies 数组。")
    return cookies


def _cookie_header_for_mtop(cookies: List[dict]) -> str:
    """合并闲鱼/淘宝相关 Cookie，同名后者覆盖（贴近浏览器行为）。"""
    bucket: Dict[str, str] = {}
    for entry in cookies:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        value = entry.get("value")
        domain = str(entry.get("domain") or "")
        if not name or value is None:
            continue
        if not any(
            token in domain
            for token in (".goofish.com", "goofish.com", ".taobao.com", "taobao.com")
        ):
            continue
        bucket[str(name)] = str(value)
    return "; ".join(f"{k}={v}" for k, v in bucket.items())


def _h5_token_from_cookie_header(cookie_header: str) -> str:
    for part in cookie_header.split(";"):
        part = part.strip()
        if part.startswith("_m_h5_tk="):
            value = part.split("=", 1)[1].strip()
            return value.split("_", 1)[0]
    raise IdleMtopError(
        "Cookie 中缺少 _m_h5_tk，请用浏览器打开闲鱼后再导出完整 state，或先访问一次 goofish.com。"
    )


def mtop_sign(token: str, timestamp_ms: str, app_key: str, data: str) -> str:
    raw = f"{token}&{timestamp_ms}&{app_key}&{data}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _build_mtop_query(*, api: str, sign: str, timestamp_ms: str) -> str:
    params = {
        "jsv": GOOFISH_MTOP_JSV,
        "appKey": GOOFISH_MTOP_APP_KEY,
        "t": timestamp_ms,
        "sign": sign,
        "v": "1.0",
        "type": "originaljson",
        "accountSite": "xianyu",
        "dataType": "json",
        "timeout": "20000",
        "api": api,
        "sessionOption": "AutoLoginOnly",
    }
    return urlencode(params)


def call_idle_mtop(
    api: str,
    path: str,
    data_obj: dict,
    *,
    cookie_header: str,
    timeout: float = 25.0,
    verify: Optional[bool] = None,
) -> dict:
    data = json.dumps(data_obj, ensure_ascii=False, separators=(",", ":"))
    timestamp_ms = str(int(time.time() * 1000))
    token = _h5_token_from_cookie_header(cookie_header)
    sign = mtop_sign(token, timestamp_ms, GOOFISH_MTOP_APP_KEY, data)
    query = _build_mtop_query(api=api, sign=sign, timestamp_ms=timestamp_ms)
    url = f"{GOOFISH_H5API_ORIGIN}{path}?{query}"
    proxies = {"http": PROXY_URL, "https": PROXY_URL} if PROXY_URL else None
    if verify is None:
        verify = os.getenv("IDLE_MTOP_VERIFY_SSL", "true").lower() not in {"0", "false", "no"}
    log_time(f"[MTOP] POST {api} data={data} verify={verify}")
    response = requests.post(
        url,
        headers={**DEFAULT_HEADERS, "cookie": cookie_header},
        data=f"data={requests.utils.quote(data)}",
        timeout=timeout,
        proxies=proxies,
        verify=verify,
    )
    log_time(f"[MTOP] HTTP {response.status_code} (len={len(response.content)})")
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise IdleMtopError(f"MTOP 响应不是 JSON 对象: {type(payload).__name__}")
    ret = payload.get("ret") or []
    ret_text = " ".join(str(x) for x in ret)
    log_time(f"[MTOP] ret={ret_text}")
    if "SUCCESS" not in ret_text:
        raise IdleMtopError(ret_text or "MTOP 调用失败")
    return payload


def fetch_idle_pc_detail(
    item_id: str,
    *,
    state_file: str,
    verify: Optional[bool] = None,
) -> dict:
    """调用 mtop.taobao.idle.pc.detail，返回完整 MTOP JSON（含 data.itemDO / sellerDO）。"""
    item_id = str(item_id).strip()
    if not item_id.isdigit():
        raise ValueError(f"无效 itemId: {item_id!r}")
    log_time(f"[MTOP] 开始拉取详情 itemId={item_id} state={state_file}")
    cookies = load_state_cookies(state_file)
    cookie_header = _cookie_header_for_mtop(cookies)
    has_tk = "_m_h5_tk=" in cookie_header
    log_time(f"[MTOP] cookie 数量={len(cookies)} 含_m_h5_tk={has_tk}")
    if not has_tk:
        raise IdleMtopError("Cookie 中缺少 _m_h5_tk，需重新导出 state")
    return call_idle_mtop(
        IDLE_PC_DETAIL_API,
        IDLE_PC_DETAIL_PATH,
        {"itemId": item_id},
        cookie_header=cookie_header,
        verify=verify,
    )


def resolve_state_file(state_file: Optional[str] = None) -> str:
    """返回账号名或路径，供 get_account_state 使用。"""
    if state_file:
        return state_file
    from src.services.account_state_store import list_account_names
    names = list_account_names()
    if names:
        return names[0]
    from src.config import STATE_FILE
    if Path(STATE_FILE).is_file():
        return STATE_FILE
    raise FileNotFoundError("未找到闲鱼登录状态，请先在账号页导入 state。")
