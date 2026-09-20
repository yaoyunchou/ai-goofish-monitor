"""清理「已删除订阅」残留的卖家商品数据（孤儿数据）。

背景：早期版本的删除订阅只删 seller_subscriptions 一行，该卖家名下的商品、
日指标、画像、健康度记录都会残留。现已改为级联删除（见
seller_subscription_storage.delete_subscription_with_stats_sync），
本脚本只用于清理**历史遗留**的孤儿数据。

判定口径：关联表里存在、但 seller_subscriptions 里已没有对应 seller_user_id
的数据，视为孤儿。

默认 **只报告不删除**（dry-run）；确认无误后加 --apply 才真正执行。

用法：
    python -m scripts.cleanup_orphan_seller_data                 # 只看报告
    python -m scripts.cleanup_orphan_seller_data --apply         # 真删
    python -m scripts.cleanup_orphan_seller_data --seller 12345  # 只处理指定卖家
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.infrastructure.persistence.db_connection import db_connection  # noqa: E402
from src.infrastructure.persistence.storage_bootstrap import bootstrap_storage  # noqa: E402
from src.services.seller_subscription_storage import (  # noqa: E402
    SELLER_RELATED_TABLES,
    delete_seller_related_data_sync,
)


# 关联表里出现过的全部卖家（UNION 去重）
_ALL_SELLERS_SQL = """
    SELECT seller_user_id FROM seller_subscription_items
    UNION
    SELECT seller_user_id FROM seller_item_daily_metrics
    UNION
    SELECT seller_user_id FROM seller_item_metrics
    UNION
    SELECT seller_user_id FROM item_monitor_health_weekly
    UNION
    SELECT seller_user_id FROM seller_profiles
    UNION
    SELECT seller_user_id FROM item_detail_api_raw WHERE seller_user_id IS NOT NULL
"""


def collect_orphan_sellers(conn, only_seller: str | None = None) -> list[dict]:
    """找出所有孤儿卖家（关联表有数据、订阅表已无记录）及其残留行数。"""
    counts = ", ".join(
        f"(SELECT COUNT(*) FROM {table} t WHERE t.seller_user_id = s.seller_user_id) AS cnt_{table}"
        for table in SELLER_RELATED_TABLES
    )
    params: tuple = ()
    filter_clause = ""
    if only_seller is not None:
        filter_clause = " AND s.seller_user_id = ?"
        params = (only_seller,)

    sql = f"""
        SELECT s.seller_user_id AS seller_user_id, {counts}
        FROM ({_ALL_SELLERS_SQL}) AS s
        WHERE NOT EXISTS (
            SELECT 1 FROM seller_subscriptions sub
            WHERE sub.seller_user_id = s.seller_user_id
        ){filter_clause}
        ORDER BY s.seller_user_id
    """
    if params:
        rows = conn.execute(sql, params).fetchall()
    else:
        rows = conn.execute(sql).fetchall()
    return [dict(row) for row in rows]


def report(rows: list[dict]) -> None:
    if not rows:
        print("[OK] 没有发现孤儿数据，无需清理。")
        return

    print(f"[WARN] 发现 {len(rows)} 个「已删除订阅」的卖家仍残留数据：\n")
    headers = [table.replace("seller_", "").replace("item_", "")[:12] for table in SELLER_RELATED_TABLES]
    print(f"{'seller_user_id':<22}" + "".join(f"{h:>14}" for h in headers))
    print("-" * (22 + 14 * len(headers)))
    for row in rows:
        counts = "".join(f"{int(row.get(f'cnt_{t}') or 0):>14}" for t in SELLER_RELATED_TABLES)
        print(f"{str(row['seller_user_id']):<22}{counts}")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="清理已删除卖家订阅的残留商品数据")
    parser.add_argument("--apply", action="store_true", help="真正执行删除（默认只报告）")
    parser.add_argument("--seller", help="只处理指定的 seller_user_id")
    args = parser.parse_args()

    bootstrap_storage()
    with db_connection() as conn:
        rows = collect_orphan_sellers(conn, args.seller)

    report(rows)
    if not rows:
        return 0
    if not args.apply:
        print("[DRY-RUN] 未做任何修改。确认上表无误后加 --apply 执行删除。")
        return 0

    total: dict[str, int] = {}
    for row in rows:
        seller_user_id = str(row["seller_user_id"])
        deleted = delete_seller_related_data_sync(seller_user_id)
        for table, count in deleted.items():
            total[table] = total.get(table, 0) + count
        summary = ", ".join(f"{k}={v}" for k, v in deleted.items() if v)
        print(f"[DELETE] {seller_user_id}: {summary}")

    print("\n[OK] 清理完成，合计：")
    for table, count in total.items():
        print(f"  {table}: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
