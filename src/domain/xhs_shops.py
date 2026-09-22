"""把看板上的商品行按店加总。缺基线的增量不写成 0。"""
from __future__ import annotations


def rollup_products(rows: list[dict]) -> dict:
    today, today_incomplete = _sum_delta(rows, "today", "today_incomplete")
    yesterday, yesterday_incomplete = _sum_delta(rows, "yesterday", "yesterday_incomplete")
    last_hour, last_hour_incomplete = _sum_delta(rows, "last_hour", "last_hour_incomplete")
    sold_values = [row["sold_total"] for row in rows if row.get("sold_total") is not None]
    return {
        "product_count": len(rows),
        "sold_total": sum(sold_values) if sold_values else None,
        "today": today,
        "today_incomplete": today_incomplete,
        "yesterday": yesterday,
        "yesterday_incomplete": yesterday_incomplete,
        "last_hour": last_hour,
        "last_hour_incomplete": last_hour_incomplete,
    }


def _sum_delta(rows: list[dict], field: str, incomplete_field: str) -> tuple[int | None, bool]:
    present = [row for row in rows if row.get(field) is not None]
    if not present:
        return None, False
    total = sum(int(row[field]) for row in present)
    incomplete = any(bool(row.get(incomplete_field)) for row in present)
    return total, incomplete
