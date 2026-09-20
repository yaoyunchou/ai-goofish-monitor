"""
调试 mtop.taobao.idle.pc.detail 直调与 SKU 解析。

用法：
    # 1) 用 itemId 调详情接口（最常用）
    python scripts/debug_idle_detail.py --item-id 997091710019

    # 2) 用商品链接（自动解析 itemId）
    python scripts/debug_idle_detail.py --link "https://www.goofish.com/item?id=997091710019"

    # 3) 指定 state 文件（默认自动找 state/*.json 或 xianyu_state.json）
    python scripts/debug_idle_detail.py --item-id 997091710019 --state state/xy699909515578.json

    # 4) 只签名不真请求（验证 sign 算法 / 看 Cookie 是否含 _m_h5_tk）
    python scripts/debug_idle_detail.py --item-id 997091710019 --dry-run

    # 5) 把原始 JSON 落盘到 data/debug/ 便于对照浏览器
    python scripts/debug_idle_detail.py --item-id 997091710019 --save

    # 6) 用本地已有的 itemDO 片段（你从 Network 复制的那种）只测解析
    python scripts/debug_idle_detail.py --parse-file data/debug/itemDO.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

# 让脚本在仓库根目录直接运行也能 import src.*
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.services.idle_mtop_client import (
    GOOFISH_H5API_ORIGIN,
    IDLE_PC_DETAIL_API,
    IDLE_PC_DETAIL_PATH,
    IdleMtopError,
    extract_item_id_from_link,
    fetch_idle_pc_detail,
    load_state_cookies,
    _cookie_header_for_mtop,
    _h5_token_from_cookie_header,
    mtop_sign,
    resolve_state_file,
)
from src.item_detail_parser import extract_skus_from_detail_payloads


def _print_section(title: str) -> None:
    print("\n" + "=" * 8 + f" {title} " + "=" * (60 - len(title)))


def _print_json(label: str, obj) -> None:
    print(f"\n--- {label} ---")
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def debug_sign_only(item_id: str, state_file: str) -> int:
    """只做签名 / Cookie 检查，不发请求。"""
    _print_section("1. 读取 state / Cookie")
    print(f"state_file = {state_file}")
    cookies = load_state_cookies(state_file)
    print(f"cookies count = {len(cookies)}")
    cookie_header = _cookie_header_for_mtop(cookies)
    print(f"cookie header (前 200 字) = {cookie_header[:200]}...")
    try:
        token = _h5_token_from_cookie_header(cookie_header)
    except IdleMtopError as exc:
        print(f"\n[FAIL] {exc}")
        print("-> 请用浏览器登录闲鱼后，重新导出 state/*.json（必须含 _m_h5_tk）。")
        return 2
    print(f"_m_h5_tk token = {token}")

    _print_section("2. 计算签名")
    data = json.dumps({"itemId": str(item_id)}, ensure_ascii=False, separators=(",", ":"))
    t = str(int(time.time() * 1000))
    sign = mtop_sign(token, t, "34839810", data)
    url = (
        f"{GOOFISH_H5API_ORIGIN}{IDLE_PC_DETAIL_PATH}"
        f"?api={IDLE_PC_DETAIL_API}&t={t}&sign={sign}&appKey=34839810&v=1.0"
    )
    print(f"data   = {data}")
    print(f"t      = {t}")
    print(f"sign   = {sign}")
    print(f"url    = {url}")
    print(f"body   = data={__import__('urllib.parse', fromlist=['quote']).quote(data)}")
    print("\n[OK] 签名计算通过。把 url + cookie + body 复制到 Postman/curl 验证即可。")
    return 0


def debug_real_call(item_id: str, state_file: str, save: bool) -> int:
    _print_section("1. 调用 mtop.taobao.idle.pc.detail")
    print(f"item_id    = {item_id}")
    print(f"state_file = {state_file}")
    t0 = time.time()
    try:
        payload = fetch_idle_pc_detail(item_id, state_file=state_file)
    except IdleMtopError as exc:
        print(f"\n[FAIL] MTOP 业务失败: {exc}")
        print("常见原因：_m_h5_tk 过期 / Cookie 失效 / 风控。重新导出 state 再试。")
        return 3
    except Exception as exc:  # noqa: BLE001
        print(f"\n[FAIL] 异常: {type(exc).__name__}: {exc}")
        return 4
    elapsed = time.time() - t0
    print(f"耗时 = {elapsed:.2f}s")

    _print_section("2. MTOP 顶层")
    print(f"ret = {payload.get('ret')}")
    print(f"v   = {payload.get('v')}")
    data = payload.get("data") or {}
    print(f"data keys = {list(data.keys()) if isinstance(data, dict) else type(data)}")

    _print_section("3. itemDO 关键字段")
    item_do = data.get("itemDO") or {}
    if not isinstance(item_do, dict) or not item_do:
        print("[WARN] 没有 data.itemDO，可能登录态失效或被风控。")
        _print_json("完整 payload", payload)
        return 5
    print(f"itemId     = {item_do.get('itemId')}")
    print(f"title      = {item_do.get('title')}")
    print(f"desc       = {(item_do.get('desc') or '')[:120]}...")
    print(f"soldPrice  = {item_do.get('soldPrice')}")
    print(f"quantity   = {item_do.get('quantity')}")
    print(f"wantCnt    = {item_do.get('wantCnt')}")
    print(f"browseCnt  = {item_do.get('browseCnt')}")
    print(f"simpleItem = {item_do.get('simpleItem')}")
    print(f"skuList    = {len(item_do.get('skuList') or [])} 条")
    print(f"idleItemSkuList = {len(item_do.get('idleItemSkuList') or [])} 条")
    print(f"imageInfos = {len(item_do.get('imageInfos') or [])} 张")
    print(f"cpvLabels  = {item_do.get('cpvLabels')}")
    print(f"itemLabelExtList = {[t.get('valueText') for t in (item_do.get('itemLabelExtList') or [])]}")

    _print_section("4. 解析 SKU")
    skus = asyncio.run(
        extract_skus_from_detail_payloads([payload], fallback_title=str(item_do.get('title') or ""))
    )
    if not skus:
        print("[WARN] 解析后 SKU 为空。")
    else:
        print(f"共 {len(skus)} 个 SKU：")
        for i, sku in enumerate(skus, 1):
            print(
                f"  #{i} sku_id={sku.get('sku_id')} label={sku.get('label')} "
                f"price={sku.get('price_display')} qty={sku.get('quantity')} "
                f"in_stock={sku.get('in_stock')}"
            )

    _print_section("5. sellerDO 关键字段（做差异分析用）")
    seller_do = data.get("sellerDO") or {}
    if isinstance(seller_do, dict) and seller_do:
        print(f"sellerId   = {seller_do.get('sellerId')}")
        print(f"nick        = {seller_do.get('nick')}")
        print(f"city        = {seller_do.get('city')}")
        print(f"hasSoldNum  = {seller_do.get('hasSoldNumInteger')}")
        print(f"replyRatio  = {seller_do.get('replyRatio24h')}")
        print(f"sellerItems = {len(seller_do.get('sellerItems') or [])} 件在售")
    else:
        print("[WARN] 没有 data.sellerDO。")

    if save:
        out_dir = ROOT / "data" / "debug"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"detail_{item_id}.json"
        out_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\n[OK] 原始 JSON 已保存: {out_file}")
    print("\n[OK] 调试完成。")
    return 0


def debug_parse_only(file_path: str) -> int:
    """只解析本地 itemDO 片段（不发请求）。"""
    path = Path(file_path)
    if not path.is_file():
        print(f"[FAIL] 文件不存在: {path}")
        return 6
    obj = json.loads(path.read_text(encoding="utf-8"))
    # 兼容两种：直接 itemDO，或完整 {data:{itemDO:...}}
    if isinstance(obj, dict) and "data" in obj and isinstance(obj["data"], dict):
        payload = obj
    elif isinstance(obj, dict) and ("itemId" in obj or "skuList" in obj):
        payload = {"data": {"itemDO": obj}}
    else:
        payload = obj
    skus = asyncio.run(
        extract_skus_from_detail_payloads([payload], fallback_title=str(
            (payload.get("data", {}).get("itemDO", {}) or {}).get("title", "")
        ))
    )
    _print_json("解析结果 SKU", skus)
    print(f"\n共 {len(skus)} 个 SKU。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="调试闲鱼商品详情 MTOP 直调")
    parser.add_argument("--item-id", help="商品 ID，如 997091710019")
    parser.add_argument("--link", help="商品链接（自动解析 itemId）")
    parser.add_argument("--state", help="state 文件路径，默认自动查找 state/*.json")
    parser.add_argument("--dry-run", action="store_true", help="只签名不真请求")
    parser.add_argument("--save", action="store_true", help="把原始 JSON 保存到 data/debug/")
    parser.add_argument("--parse-file", help="只解析本地 JSON 文件，不联网")
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="跳过 SSL 证书校验（调试用，Windows 公司代理/CA 不全时开启）",
    )
    args = parser.parse_args()

    if args.parse_file:
        return debug_parse_only(args.parse_file)

    item_id = (args.item_id or "").strip()
    if not item_id and args.link:
        item_id = extract_item_id_from_link(args.link) or ""
    if not item_id:
        parser.error("需要 --item-id 或 --link 或 --parse-file")

    try:
        state_file = args.state or resolve_state_file(None)
    except FileNotFoundError as exc:
        print(f"[FAIL] {exc}")
        print("-> 请先在 Web 账号页导入 state，或把 xianyu_state.json 放到仓库根目录。")
        return 1

    if args.insecure:
        os.environ["IDLE_MTOP_VERIFY_SSL"] = "false"

    if args.dry_run:
        return debug_sign_only(item_id, state_file)
    return debug_real_call(item_id, state_file, args.save)


if __name__ == "__main__":
    raise SystemExit(main())
