"""小红书商品与快照。快照只插入，不按日覆盖。"""
from __future__ import annotations

from datetime import datetime, timedelta

from src.domain.xhs_analytics import (
    SnapshotPoint,
    daily_series,
    delta_from_levels,
    floor_hour,
    hourly_series,
    day_start,
)
from src.domain.xhs_import import parse_import_workbook
from src.domain.xhs_labels import normalize_category, normalize_shop_name, normalize_tags
from src.domain.xhs_parse import is_short_link, parse_product_id, parse_public_html
from src.domain.xhs_shops import rollup_products
from src.infrastructure.persistence.db_connection import db_connection
from src.infrastructure.persistence.sql_dialect import json_text, parse_json_field
from src.time_utils import shanghai_now
from src.xhs_collector import collect_round, fetch_public

DEFAULT_CRON = "0 * * * *"

_PRODUCT_SELECT = """
    SELECT p.id, p.source_url, p.title, p.shop_name, p.cover_url, p.price,
           p.active, p.last_error, p.last_status, p.updated_at,
           p.shop_id, p.category, p.tags_json, s.name AS assigned_shop_name
    FROM xhs_products p
    LEFT JOIN xhs_shops s ON s.id = p.shop_id
"""


class ShortLinkBlocked(Exception):
    """公开页拒绝访问，导入应停掉后续短链。"""


def _row_time(value) -> datetime:
    if isinstance(value, datetime):
        return value
    text = str(value).replace("Z", "+00:00")
    return datetime.fromisoformat(text)


def add_product(
    url_or_id: str,
    *,
    shop_name: str | None = None,
    category: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    """加入监控。空的店铺、分类、标记在商品已存在时不覆盖。"""
    source_url = (url_or_id or "").strip()
    if not source_url:
        raise ValueError("请填写商品链接")
    product_id = parse_product_id(source_url)
    if product_id is None and is_short_link(source_url):
        fetched = fetch_public(source_url)
        if fetched.status == 461:
            raise ShortLinkBlocked("公开页返回 461，已停止后续短链")
        fields = parse_public_html(fetched.body, fetched.status)
        if fields.login_required:
            raise ShortLinkBlocked("公开页要求登录，已停止后续短链")
        product_id = parse_product_id(fetched.final_url)
        if fetched.final_url.startswith("http"):
            source_url = fetched.final_url
    if product_id is None:
        raise ValueError("无法从链接解析商品 ID，请粘贴商品页链接或商品 ID")
    if not source_url.startswith("http"):
        source_url = f"https://www.xiaohongshu.com/goods-detail/{product_id}"
    shop = normalize_shop_name(shop_name)
    label = normalize_category(category)
    tag_list = normalize_tags(tags) if tags else None
    with db_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM xhs_products WHERE id = ?",
            (product_id,),
        ).fetchone()
        shop_id = _ensure_shop(conn, shop) if shop else None
        if existing is None:
            conn.execute(
                """
                INSERT INTO xhs_products (
                    id, source_url, active, shop_id, category, tags_json, updated_at
                )
                VALUES (?, ?, TRUE, ?, ?, ?, now())
                """,
                (product_id, source_url, shop_id, label, json_text(tag_list or [])),
            )
        else:
            assignments = [
                "source_url = ?",
                "active = TRUE",
                "last_status = NULL",
                "last_error = NULL",
                "updated_at = now()",
            ]
            params: list = [source_url]
            if shop_id is not None:
                assignments.append("shop_id = ?")
                params.append(shop_id)
            if label is not None:
                assignments.append("category = ?")
                params.append(label)
            if tag_list:
                assignments.append("tags_json = ?")
                params.append(json_text(tag_list))
            params.append(product_id)
            conn.execute(
                f"UPDATE xhs_products SET {', '.join(assignments)} WHERE id = ?",
                tuple(params),
            )
        conn.commit()
    product = get_product(product_id)
    product["created"] = existing is None
    return product


def list_board(now: datetime | None = None) -> list[dict]:
    current = now or shanghai_now()
    today0 = day_start(current)
    yesterday0 = today0 - timedelta(days=1)
    this_hour = floor_hour(current)
    prev_hour = this_hour - timedelta(hours=1)
    with db_connection() as conn:
        products = conn.execute(
            _PRODUCT_SELECT
            + " WHERE p.active = TRUE AND (p.last_status IS NULL OR p.last_status NOT IN ('failed', 'skipped', 'delisted'))"
            + " ORDER BY p.created_at DESC"
        ).fetchall()
        levels = conn.execute(
            """
            SELECT product_id,
                   MAX(sold) FILTER (WHERE captured_at <= ? AND sold IS NOT NULL) AS hw_now,
                   MAX(sold) FILTER (WHERE captured_at <= ? AND sold IS NOT NULL) AS hw_today,
                   MAX(sold) FILTER (WHERE captured_at <= ? AND sold IS NOT NULL) AS hw_yesterday,
                   MAX(sold) FILTER (WHERE captured_at <= ? AND sold IS NOT NULL) AS hw_hour,
                   MAX(sold) FILTER (WHERE captured_at <= ? AND sold IS NOT NULL) AS hw_prev_hour
            FROM xhs_snapshots
            GROUP BY product_id
            """,
            (current, today0, yesterday0, this_hour, prev_hour),
        ).fetchall()
        first_today = _first_sold_map(conn, today0, current)
        first_yesterday = _first_sold_map(conn, yesterday0, today0)
        first_hour = _first_sold_map(conn, prev_hour, this_hour)
    level_map = {row["product_id"]: row for row in levels}
    rows = []
    for product in products:
        level = level_map.get(product["id"], {})
        price = product.get("price")
        today = delta_from_levels(
            level.get("hw_today"),
            level.get("hw_now"),
            first_today.get(product["id"]),
            allow_incomplete_baseline=True,
            price=price,
        )
        yesterday = delta_from_levels(
            level.get("hw_yesterday"),
            level.get("hw_today"),
            first_yesterday.get(product["id"]),
            allow_incomplete_baseline=True,
            price=price,
        )
        last_hour = delta_from_levels(
            level.get("hw_prev_hour"),
            level.get("hw_hour"),
            first_hour.get(product["id"]),
            allow_incomplete_baseline=True,
            price=price,
        )
        rows.append(
            {
                **_public_product(product),
                "sold_total": level.get("hw_now"),
                "today": today.delta,
                "today_incomplete": today.incomplete if today.delta is not None else False,
                "today_fuzzy": today.fuzzy_amount,
                "yesterday": yesterday.delta,
                "yesterday_incomplete": yesterday.incomplete if yesterday.delta is not None else False,
                "last_hour": last_hour.delta,
                "last_hour_incomplete": last_hour.incomplete if last_hour.delta is not None else False,
            }
        )
    return rows


def _first_sold_map(conn, start: datetime, end: datetime) -> dict[str, int]:
    rows = conn.execute(
        """
        SELECT DISTINCT ON (product_id) product_id, sold
        FROM xhs_snapshots
        WHERE sold IS NOT NULL
          AND captured_at > ?
          AND captured_at <= ?
        ORDER BY product_id, captured_at ASC
        """,
        (start, end),
    ).fetchall()
    return {row["product_id"]: row["sold"] for row in rows}


def get_product(product_id: str) -> dict:
    with db_connection() as conn:
        row = conn.execute(
            _PRODUCT_SELECT + " WHERE p.id = ?",
            (product_id,),
        ).fetchone()
    if row is None:
        raise KeyError(product_id)
    return _public_product(row)


def list_products_by_status(statuses: tuple[str, ...]) -> list[dict]:
    if not statuses:
        return []
    placeholders = ", ".join("?" for _ in statuses)
    with db_connection() as conn:
        rows = conn.execute(
            _PRODUCT_SELECT
            + f" WHERE p.active = TRUE AND p.last_status IN ({placeholders}) ORDER BY p.updated_at DESC",
            statuses,
        ).fetchall()
    return [_public_product(row) for row in rows]


def ignore_failures(product_ids: list[str]) -> int:
    ids = [item for item in product_ids if item]
    if not ids:
        return 0
    placeholders = ", ".join("?" for _ in ids)
    with db_connection() as conn:
        cursor = conn.execute(
            f"""
            UPDATE xhs_products
            SET last_status = NULL, last_error = NULL, updated_at = now()
            WHERE active = TRUE
              AND last_status IN ('failed', 'skipped')
              AND id IN ({placeholders})
            """,
            tuple(ids),
        )
        conn.commit()
        return cursor.rowcount


def deactivate_product(product_id: str) -> None:
    with db_connection() as conn:
        conn.execute(
            "UPDATE xhs_products SET active = FALSE, updated_at = now() WHERE id = ?",
            (product_id,),
        )
        conn.commit()


def load_points(product_id: str) -> list[SnapshotPoint]:
    with db_connection() as conn:
        rows = conn.execute(
            """
            SELECT captured_at, sold, price
            FROM xhs_snapshots
            WHERE product_id = ?
            ORDER BY captured_at ASC, id ASC
            """,
            (product_id,),
        ).fetchall()
    return [
        SnapshotPoint(_row_time(row["captured_at"]), row["sold"], row["price"])
        for row in rows
    ]


def product_series(product_id: str, kind: str, now: datetime | None = None) -> list[dict]:
    current = now or shanghai_now()
    points = load_points(product_id)
    if kind == "daily":
        return daily_series(points, current, days=7)
    return hourly_series(points, current, current)


def get_schedule() -> dict:
    with db_connection() as conn:
        row = conn.execute(
            "SELECT cron, enabled FROM xhs_schedule WHERE id = 1"
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO xhs_schedule (id, cron, enabled) VALUES (1, ?, FALSE)",
                (DEFAULT_CRON,),
            )
            conn.commit()
            return {"cron": DEFAULT_CRON, "enabled": False}
    return {"cron": row["cron"], "enabled": bool(row["enabled"])}


def save_schedule(cron: str, enabled: bool) -> dict:
    expression = (cron or "").strip() or DEFAULT_CRON
    with db_connection() as conn:
        conn.execute(
            """
            INSERT INTO xhs_schedule (id, cron, enabled, updated_at)
            VALUES (1, ?, ?, now())
            ON CONFLICT (id) DO UPDATE
                SET cron = EXCLUDED.cron,
                    enabled = EXCLUDED.enabled,
                    updated_at = now()
            """,
            (expression, enabled),
        )
        conn.commit()
    return {"cron": expression, "enabled": enabled}


def apply_collect_results(results: list) -> dict:
    saved = 0
    failed = 0
    with db_connection() as conn:
        for item in results:
            if item.delisted:
                conn.execute(
                    """
                    UPDATE xhs_products
                    SET last_error = ?, last_status = 'delisted', updated_at = now(),
                        title = COALESCE(?, title),
                        shop_name = COALESCE(?, shop_name),
                        cover_url = COALESCE(?, cover_url)
                    WHERE id = ?
                    """,
                    (item.error or "商品已下架", item.title, item.shop_name, item.cover_url, item.product_id),
                )
                continue
            if item.skipped:
                failed += 1
                conn.execute(
                    """
                    UPDATE xhs_products
                    SET last_error = ?, last_status = 'skipped', updated_at = now()
                    WHERE id = ?
                    """,
                    (item.error, item.product_id),
                )
                continue
            if not item.ok or item.sold is None:
                failed += 1
                conn.execute(
                    """
                    UPDATE xhs_products
                    SET last_error = ?, last_status = 'failed', updated_at = now(),
                        title = COALESCE(?, title),
                        cover_url = COALESCE(?, cover_url)
                    WHERE id = ?
                    """,
                    (item.error or "未解析到累计已售", item.title, item.cover_url, item.product_id),
                )
                continue
            conn.execute(
                """
                UPDATE xhs_products
                SET title = COALESCE(?, title),
                    shop_name = COALESCE(?, shop_name),
                    cover_url = COALESCE(?, cover_url),
                    price = COALESCE(?, price),
                    source_url = COALESCE(?, source_url),
                    shop_id = COALESCE(shop_id, ?),
                    last_error = NULL,
                    last_status = 'ok',
                    updated_at = now()
                WHERE id = ?
                """,
                (
                    item.title,
                    item.shop_name,
                    item.cover_url,
                    item.price,
                    item.final_url,
                    _shop_id_if_unassigned(conn, item.product_id, item.shop_name),
                    item.product_id,
                ),
            )
            conn.execute(
                """
                INSERT INTO xhs_snapshots (product_id, captured_at, sold, price, raw_note)
                VALUES (?, ?, ?, ?, ?)
                """,
                (item.product_id, item.captured_at, item.sold, item.price, item.note),
            )
            saved += 1
        conn.commit()
    return {"saved": saved, "failed": failed, "total": len(results)}


def collect_products(product_ids: list[str] | None = None, fetch=None) -> dict:
    with db_connection() as conn:
        if product_ids:
            placeholders = ", ".join("?" for _ in product_ids)
            rows = conn.execute(
                f"""
                SELECT id, source_url FROM xhs_products
                WHERE active = TRUE
                  AND (last_status IS NULL OR last_status <> 'delisted')
                  AND id IN ({placeholders})
                """,
                tuple(product_ids),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, source_url FROM xhs_products
                WHERE active = TRUE AND (last_status IS NULL OR last_status <> 'delisted')
                ORDER BY created_at
                """
            ).fetchall()
    targets = [{"id": row["id"], "source_url": row["source_url"]} for row in rows]
    results = collect_round(targets, fetch=fetch)
    summary = apply_collect_results(results)
    summary["stopped"] = any(item.blocked for item in results)
    return summary


def collect_one(product_id: str, fetch=None) -> dict:
    return collect_products([product_id], fetch=fetch)


def update_labels(
    product_id: str,
    *,
    shop_name: str | None,
    category: str | None,
    tags: list[str],
) -> dict:
    shop = normalize_shop_name(shop_name)
    label = normalize_category(category)
    tag_list = normalize_tags(tags)
    with db_connection() as conn:
        row = conn.execute(
            "SELECT id FROM xhs_products WHERE id = ? AND active = TRUE",
            (product_id,),
        ).fetchone()
        if row is None:
            raise KeyError(product_id)
        shop_id = _ensure_shop(conn, shop) if shop else None
        conn.execute(
            """
            UPDATE xhs_products
            SET shop_id = ?, category = ?, tags_json = ?, updated_at = now()
            WHERE id = ?
            """,
            (shop_id, label, json_text(tag_list), product_id),
        )
        conn.commit()
    return get_product(product_id)


def list_shops(now: datetime | None = None) -> dict:
    board = list_board(now)
    with db_connection() as conn:
        shops = conn.execute(
            "SELECT id, name FROM xhs_shops ORDER BY name"
        ).fetchall()
    grouped: dict[int, list[dict]] = {}
    unassigned = []
    for row in board:
        if row.get("shop_id") is None:
            unassigned.append(row)
            continue
        grouped.setdefault(int(row["shop_id"]), []).append(row)
    items = []
    for shop in shops:
        shop_rows = grouped.get(int(shop["id"]), [])
        items.append({"id": shop["id"], "name": shop["name"], **rollup_products(shop_rows)})
    return {
        "items": items,
        "unassigned": {
            **rollup_products(unassigned),
            "items": unassigned,
        },
    }


def get_shop(shop_id: int, now: datetime | None = None) -> dict:
    with db_connection() as conn:
        shop = conn.execute(
            "SELECT id, name FROM xhs_shops WHERE id = ?",
            (shop_id,),
        ).fetchone()
    if shop is None:
        raise KeyError(shop_id)
    rows = [row for row in list_board(now) if row.get("shop_id") is not None and int(row["shop_id"]) == int(shop_id)]
    return {"id": shop["id"], "name": shop["name"], **rollup_products(rows), "items": rows}


def create_shop(name: str) -> dict:
    shop = normalize_shop_name(name)
    if shop is None:
        raise ValueError("请填写店铺名")
    with db_connection() as conn:
        shop_id = _ensure_shop(conn, shop)
        conn.commit()
        row = conn.execute(
            "SELECT id, name FROM xhs_shops WHERE id = ?",
            (shop_id,),
        ).fetchone()
    return {"id": row["id"], "name": row["name"]}


def import_product_rows(payload: bytes) -> dict:
    parsed = parse_import_workbook(payload)
    added = 0
    updated = 0
    failed: list[dict] = []
    blocked = False
    for row in parsed:
        url = row["url"]
        if blocked and is_short_link(url):
            failed.append({"row": row["row"], "reason": "公开页已停止，短链未再解析"})
            continue
        try:
            saved = add_product(
                url,
                shop_name=row["shop"],
                category=row["category"],
                tags=row["tags"],
            )
        except ShortLinkBlocked as exc:
            blocked = True
            failed.append({"row": row["row"], "reason": str(exc)})
            continue
        except ValueError as exc:
            failed.append({"row": row["row"], "reason": str(exc)})
            continue
        if saved.get("created"):
            added += 1
        else:
            updated += 1
    return {"added": added, "updated": updated, "failed": failed}


def _public_product(row) -> dict:
    data = dict(row)
    tags = parse_json_field(data.pop("tags_json", None), default=[])
    data["tags"] = [str(item) for item in tags] if isinstance(tags, list) else []
    if data.get("shop_id") is not None:
        data["shop_id"] = int(data["shop_id"])
    return data


def _ensure_shop(conn, name: str) -> int:
    conn.execute(
        "INSERT INTO xhs_shops (name) VALUES (?) ON CONFLICT (name) DO NOTHING",
        (name,),
    )
    row = conn.execute("SELECT id FROM xhs_shops WHERE name = ?", (name,)).fetchone()
    return int(row["id"])


def _shop_id_if_unassigned(conn, product_id: str, shop_name: str | None) -> int | None:
    current = conn.execute(
        "SELECT shop_id FROM xhs_products WHERE id = ?",
        (product_id,),
    ).fetchone()
    if current and current["shop_id"] is not None:
        return None
    try:
        label = normalize_shop_name(shop_name)
    except ValueError:
        return None
    if label is None:
        return None
    return _ensure_shop(conn, label)
