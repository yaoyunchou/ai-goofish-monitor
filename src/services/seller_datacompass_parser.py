"""解析闲鱼卖家工作台 datacompass API。"""
from __future__ import annotations

from typing import Any


PARSER_VERSION = "1"


def _unwrap_payload(raw: dict | None) -> dict:
    payload = raw or {}
    data = payload.get("data")
    if isinstance(data, dict) and isinstance(data.get("data"), dict):
        return data["data"]
    if isinstance(data, dict):
        return data
    return payload


def _normalize_metric(item: dict | None) -> dict[str, Any]:
    item = item or {}
    value = item.get("data")
    prev = item.get("lastData")
    ratio = item.get("ratio")
    return {
        "name": item.get("name"),
        "value": value,
        "prev": prev,
        "ratio": ratio,
        "ratio_format": item.get("ratioFormat"),
        "display": item.get("dataStr") or item.get("dataFormat"),
        "prev_display": item.get("lastDataStr") or item.get("lastDataFormat"),
        "cycle": item.get("cycle"),
    }


def parse_banner_metrics(raw: dict | None) -> dict[str, Any]:
    inner = _unwrap_payload(raw)
    banner_list = (
        (inner.get("graphBannerBenchData") or {}).get("bannerDataList") or []
    )
    metrics = {}
    for item in banner_list:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        metrics[item["name"]] = _normalize_metric(item)
    date_range = ((raw or {}).get("data") or {}).get("extendInfo", {}).get("realDateRange")
    if not date_range:
        date_range = inner.get("extendInfo", {}).get("realDateRange") if isinstance(inner, dict) else None
    return {
        "parser_version": PARSER_VERSION,
        "date_range": date_range or [],
        "metrics": metrics,
    }


def parse_flow_detail(raw: dict | None) -> dict[str, Any]:
    inner = _unwrap_payload(raw)
    flow = inner.get("itemFlowTransferData") or inner
    metrics = {}
    if isinstance(flow, dict):
        for key, value in flow.items():
            if isinstance(value, dict) and ("name" in value or "data" in value):
                metrics[value.get("name") or key] = _normalize_metric(value)
            elif not isinstance(value, (dict, list)):
                metrics[key] = {
                    "name": key,
                    "value": value,
                    "prev": None,
                    "ratio": None,
                }
        if isinstance(flow.get("graphBannerBenchData"), dict):
            metrics.update(parse_banner_metrics({"data": {"data": flow}})["metrics"])
    result = parse_banner_metrics(raw)
    result["metrics"].update(metrics)
    result["scene"] = inner.get("scene") or flow.get("scene") if isinstance(flow, dict) else None
    result["time_cycle"] = inner.get("timeCycle") or flow.get("timeCycle") if isinstance(flow, dict) else None
    return result


def parse_refund_summary(raw: dict | None) -> dict[str, Any]:
    inner = _unwrap_payload(raw)
    metrics = {}
    for key, value in inner.items():
        if isinstance(value, dict) and ("data" in value or "name" in value):
            metrics[value.get("name") or key] = _normalize_metric(value)
        elif not isinstance(value, (dict, list)):
            metrics[key] = {
                "name": key,
                "value": value,
                "prev": None,
                "ratio": None,
            }
    date_range = ((raw or {}).get("data") or {}).get("extendInfo", {}).get("realDateRange") or []
    return {
        "parser_version": PARSER_VERSION,
        "date_range": date_range,
        "metrics": metrics,
    }


def parse_browse_summary(raw: dict | None) -> dict[str, Any]:
    inner = _unwrap_payload(raw)
    buckets: dict[str, list] = {
        "time": [],
        "region": [],
        "category": [],
        "source": [],
    }
    mapping = {
        "time_range": "time",
        "city": "region",
        "cate": "category",
        "scene": "source",
    }
    for key in ("buyerActiveList", "buyerProvinceList", "buyerCateList", "buyerSceneList"):
        rows = inner.get(key) or []
        for row in rows:
            if not isinstance(row, dict):
                continue
            bucket = mapping.get(row.get("profileCode"), "source")
            buckets[bucket].append({
                "label": row.get("profileVal"),
                "count": row.get("usrCnt"),
                "ratio": row.get("usrRatio"),
                "ratio_format": row.get("usrRatioFormat"),
            })
    date_range = ((raw or {}).get("data") or {}).get("extendInfo", {}).get("realDateRange") or []
    return {
        "parser_version": PARSER_VERSION,
        "date_range": date_range,
        "distribution": buckets,
    }


API_PARSERS = {
    "mtop.alibaba.idle.seller.pc.datacompass.singleuser.seller.summary": parse_banner_metrics,
    "mtop.alibaba.idle.seller.pc.datacompass.singleuser.item.summary": parse_banner_metrics,
    "mtop.alibaba.idle.seller.pc.datacompass.singleuser.repurchase.summary": parse_banner_metrics,
    "mtop.alibaba.idle.seller.pc.datacompass.flow.detail": parse_flow_detail,
    "mtop.alibaba.idle.seller.pc.datacompass.refund.summary": parse_refund_summary,
    "mtop.alibaba.idle.seller.pc.datacompass.singleuser.browse.summary": parse_browse_summary,
}

SHORT_API_NAMES = {
    "mtop.alibaba.idle.seller.pc.datacompass.singleuser.seller.summary": "seller.summary",
    "mtop.alibaba.idle.seller.pc.datacompass.singleuser.item.summary": "item.summary",
    "mtop.alibaba.idle.seller.pc.datacompass.singleuser.repurchase.summary": "repurchase.summary",
    "mtop.alibaba.idle.seller.pc.datacompass.flow.detail": "flow.detail",
    "mtop.alibaba.idle.seller.pc.datacompass.refund.summary": "refund.summary",
    "mtop.alibaba.idle.seller.pc.datacompass.singleuser.browse.summary": "browse.summary",
}


def parse_datacompass_api(api_name: str, raw: dict | None) -> dict[str, Any] | None:
    parser = API_PARSERS.get(api_name)
    if not parser:
        return None
    parsed = parser(raw)
    parsed["api_name"] = SHORT_API_NAMES.get(api_name, api_name)
    parsed["full_api_name"] = api_name
    return parsed
