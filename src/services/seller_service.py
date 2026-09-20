"""关注卖家服务：关注/取消关注/列表/刷新商品。"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.infrastructure.persistence.db_connection import db_connection
from src.infrastructure.persistence.sql_dialect import json_text, parse_json_field
from src.utils import log_time


def _now() -> str:
    return datetime.now().isoformat()


def follow_seller(seller_id: str, *, seller_name: str = "", avatar_url: str = "",
                   city: str = "", cron: str = "0 */6 * * *", note: str = "") -> Dict[str, Any]:
    """关注卖家。若 goofish_sellers 无此卖家则先创建占位行。"""
    sid = str(seller_id)
    with db_connection() as conn:
        conn.execute(
            """INSERT INTO goofish_sellers (seller_id, unique_name, portrait_url, city, raw_json, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s)
            ON CONFLICT (seller_id) DO UPDATE SET
                unique_name=COALESCE(EXCLUDED.unique_name, goofish_sellers.unique_name),
                portrait_url=COALESCE(EXCLUDED.portrait_url, goofish_sellers.portrait_url),
                city=COALESCE(EXCLUDED.city, goofish_sellers.city),
                updated_at=EXCLUDED.updated_at""",
            (sid, seller_name or None, avatar_url or None, city or None,
             json_text({}), _now()),
        )
        conn.execute(
            """INSERT INTO followed_sellers (seller_id, cron, follow_at, note)
            VALUES (%s,%s,%s,%s)
            ON CONFLICT (seller_id) DO UPDATE SET note=EXCLUDED.note""",
            (sid, cron, _now(), note or None),
        )
        conn.commit()
    log_time(f"[关注卖家] 已关注 seller_id={sid} name={seller_name}")
    return {"seller_id": sid, "seller_name": seller_name, "followed": True}


def unfollow_seller(seller_id: str) -> bool:
    sid = str(seller_id)
    with db_connection() as conn:
        cur = conn.execute("DELETE FROM followed_sellers WHERE seller_id = %s", (sid,))
        conn.commit()
        deleted = cur.rowcount > 0
    if deleted:
        log_time(f"[关注卖家] 已取消关注 seller_id={sid}")
    return deleted


def list_followed_sellers() -> List[Dict[str, Any]]:
    with db_connection() as conn:
        rows = conn.execute(
            """SELECT fs.seller_id, fs.cron, fs.follow_at, fs.last_fetch_at,
                      fs.last_fetch_status, fs.last_fetch_error, fs.note,
                      gs.unique_name, gs.portrait_url, gs.city, gs.signature,
                      gs.item_count, gs.has_sold_num, gs.new_good_ratio_rate,
                      gs.user_reg_day, gs.xianyu_summary
               FROM followed_sellers fs
               LEFT JOIN goofish_sellers gs ON gs.seller_id = fs.seller_id
               ORDER BY fs.follow_at DESC"""
        ).fetchall()
        return [dict(r) for r in rows]


def get_followed_seller(seller_id: str) -> Optional[Dict[str, Any]]:
    sid = str(seller_id)
    with db_connection() as conn:
        row = conn.execute(
            """SELECT fs.*, gs.unique_name, gs.portrait_url, gs.city, gs.signature,
                      gs.item_count, gs.has_sold_num, gs.new_good_ratio_rate,
                      gs.user_reg_day, gs.xianyu_summary, gs.reply_ratio_24h,
                      gs.reply_interval, gs.last_visit_time, gs.zhima_auth,
                      gs.remark_good_cnt, gs.remark_default_cnt, gs.remark_bad_cnt
               FROM followed_sellers fs
               LEFT JOIN goofish_sellers gs ON gs.seller_id = fs.seller_id
               WHERE fs.seller_id = %s""",
            (sid,),
        ).fetchone()
        return dict(row) if row else None


def get_seller_items(seller_id: str, *, sort_by: str = "want_cnt",
                     limit: int = 100) -> List[Dict[str, Any]]:
    """获取卖家最新快照商品列表，支持按热度排序。"""
    sid = str(seller_id)
    sort_map = {
        "want_cnt": "want_cnt DESC NULLS LAST",
        "browse_cnt": "browse_cnt DESC NULLS LAST",
        "sold_cnt": "sold_cnt DESC NULLS LAST",
        "price": "price ASC",
        "fetched_at": "fetched_at DESC",
    }
    order = sort_map.get(sort_by, sort_map["want_cnt"])
    with db_connection() as conn:
        rows = conn.execute(
            f"""SELECT DISTINCT ON (item_id) item_id, title, price, pic_url, status,
                       want_cnt, browse_cnt, collect_cnt, sold_cnt, fetched_at
                FROM seller_item_snapshots
                WHERE seller_id = %s
                ORDER BY item_id, fetched_at DESC, {order}
                LIMIT %s""",
            (sid, limit),
        ).fetchall()
        results = [dict(r) for r in rows]
        results.sort(key=lambda x: (x.get(sort_by) is None, -(x.get(sort_by) or 0)))
        return results


def update_seller_cron(seller_id: str, cron: str) -> bool:
    sid = str(seller_id)
    with db_connection() as conn:
        cur = conn.execute(
            "UPDATE followed_sellers SET cron = %s WHERE seller_id = %s",
            (cron, sid),
        )
        conn.commit()
        return cur.rowcount > 0


async def refresh_seller_items(seller_id: str, *, top_n_detail: int = 10) -> Dict[str, Any]:
    """拉取卖家最新商品列表并写入快照表，对前 N 个商品调详情API补热度。"""
    sid = str(seller_id)
    log_time(f"[关注卖家] 开始刷新 seller_id={sid}")
    with db_connection() as conn:
        conn.execute(
            "UPDATE followed_sellers SET last_fetch_status = 'running', last_fetch_error = NULL WHERE seller_id = %s",
            (sid,),
        )
        conn.commit()

    try:
        items = await _fetch_seller_items_via_playwright(sid)
        now = _now()
        with db_connection() as conn:
            for item in items:
                conn.execute(
                    """INSERT INTO seller_item_snapshots
                       (seller_id, item_id, title, price, pic_url, status, want_cnt, browse_cnt, collect_cnt, sold_cnt, fetched_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (sid, item.get("item_id"), item.get("title"), item.get("price"),
                     item.get("pic_url"), item.get("status"),
                     item.get("want_cnt"), item.get("browse_cnt"),
                     item.get("collect_cnt"), item.get("sold_cnt"), now),
                )
            conn.execute(
                "UPDATE followed_sellers SET last_fetch_status = 'done', last_fetch_at = %s, last_fetch_error = NULL WHERE seller_id = %s",
                (now, sid),
            )
            conn.commit()
        log_time(f"[关注卖家] 列表刷新完成 seller_id={sid} items={len(items)}")

        if top_n_detail > 0 and items:
            await _enrich_top_items_with_detail(sid, items[:top_n_detail])
        return {"seller_id": sid, "status": "done", "items_count": len(items)}
    except Exception as exc:
        err = str(exc)
        log_time(f"[关注卖家] 刷新失败 seller_id={sid}: {type(exc).__name__}: {err}")
        with db_connection() as conn:
            conn.execute(
                "UPDATE followed_sellers SET last_fetch_status = 'failed', last_fetch_at = %s, last_fetch_error = %s WHERE seller_id = %s",
                (_now(), err, sid),
            )
            conn.commit()
        return {"seller_id": sid, "status": "failed", "error": err}


async def _fetch_seller_items_via_playwright(seller_id: str) -> List[Dict[str, Any]]:
    """用 Playwright 访问卖家主页，捕获商品列表 API。"""
    from playwright.async_api import async_playwright
    from src.config import RUN_HEADLESS
    from src.scraper import _resolve_browser_channel, _default_context_options
    from src.services.account_state_store import resolve_for_playwright

    state_data, state_name = resolve_for_playwright(resolve_state_file())
    captured: List[dict] = []

    async def on_response(response):
        url = response.url or ""
        if "mtop.idle.web.xyh.item.list" not in url:
            return
        try:
            data = await response.json()
            cards = data.get("data", {}).get("cardList", []) or []
            captured.extend(cards)
        except Exception:
            pass

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=RUN_HEADLESS,
            channel=_resolve_browser_channel(),
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        ctx = await browser.new_context(storage_state=state_data, **_default_context_options())
        page = await ctx.new_page()
        page.on("response", on_response)
        try:
            await page.goto(f"https://www.goofish.com/personal?userId={seller_id}",
                            wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
            for _ in range(10):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)
        finally:
            await ctx.close()
            await browser.close()

    items = []
    for card in captured:
        cd = card.get("cardData") or {}
        items.append({
            "item_id": str(cd.get("id") or ""),
            "title": cd.get("title") or "",
            "price": str((cd.get("priceInfo") or {}).get("price") or ""),
            "pic_url": (cd.get("picInfo") or {}).get("picUrl") or "",
            "status": "在售" if cd.get("itemStatus") == 0 else "已售" if cd.get("itemStatus") == 1 else "",
            "want_cnt": cd.get("wantCnt"),
            "browse_cnt": cd.get("browseCnt"),
            "collect_cnt": cd.get("collectCnt"),
        })
    return items


def resolve_state_file() -> str:
    from src.services.account_state_store import list_account_names
    names = list_account_names()
    if names:
        return names[0]
    raise FileNotFoundError("未找到闲鱼登录状态")


async def _enrich_top_items_with_detail(seller_id: str, items: List[Dict[str, Any]]) -> None:
    """对前 N 个商品调详情 API 补充 want/browse/collect/sold 数据。"""
    from src.services.idle_mtop_client import fetch_idle_pc_detail

    state_file = resolve_state_file()
    now = _now()
    enriched = 0
    for item in items:
        iid = item.get("item_id")
        if not iid or not str(iid).isdigit():
            continue
        try:
            resp = await asyncio.to_thread(fetch_idle_pc_detail, str(iid), state_file=state_file)
            data = resp.get("data") or {}
            ido = data.get("itemDO") or {}
            item["want_cnt"] = ido.get("wantCnt")
            item["browse_cnt"] = ido.get("browseCnt")
            item["collect_cnt"] = ido.get("collectCnt")
            item["sold_cnt"] = ido.get("soldCnt")
            with db_connection() as conn:
                conn.execute(
                    """UPDATE seller_item_snapshots SET want_cnt=%s, browse_cnt=%s, collect_cnt=%s, sold_cnt=%s
                       WHERE seller_id=%s AND item_id=%s AND fetched_at=%s""",
                    (ido.get("wantCnt"), ido.get("browseCnt"), ido.get("collectCnt"),
                     ido.get("soldCnt"), seller_id, iid, now),
                )
                conn.commit()
            enriched += 1
        except Exception as exc:
            log_time(f"[关注卖家] 详情补充失败 item={iid}: {type(exc).__name__}: {exc}")
    if enriched:
        log_time(f"[关注卖家] 详情补充完成 seller={seller_id} enriched={enriched}")


async def refresh_all_sellers() -> List[Dict[str, Any]]:
    """批量刷新所有关注卖家。"""
    sellers = list_followed_sellers()
    results = []
    for s in sellers:
        sid = s["seller_id"]
        try:
            r = await refresh_seller_items(sid)
            results.append(r)
        except Exception as exc:
            results.append({"seller_id": sid, "status": "failed", "error": str(exc)})
    return results
