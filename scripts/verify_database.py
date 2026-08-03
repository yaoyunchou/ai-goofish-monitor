#!/usr/bin/env python3
"""
验证当前 DATABASE_DRIVER 配置下的数据库连通性与核心表读写。

用法:
  python -m scripts.verify_database
  DATABASE_DRIVER=postgres python -m scripts.verify_database
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

load_dotenv(_REPO_ROOT / ".env", override=False)

from src.infrastructure.persistence.database_config import (  # noqa: E402
    get_database_driver,
    get_postgres_dsn,
    is_postgres,
)
from src.infrastructure.persistence.db_connection import db_connection  # noqa: E402


CORE_TABLES = (
    "app_metadata",
    "tasks",
    "result_items",
    "price_snapshots",
    "result_blacklist_rules",
    "collected_items",
)


def _mask_dsn(dsn: str) -> str:
    if "@" not in dsn:
        return dsn
    prefix, rest = dsn.split("@", 1)
    if "://" in prefix:
        scheme, _auth = prefix.split("://", 1)
        return f"{scheme}://***@{rest}"
    return f"***@{rest}"


def main() -> int:
    driver = get_database_driver()
    print(f"DATABASE_DRIVER={driver}")
    if is_postgres():
        dsn = get_postgres_dsn()
        print(f"DATABASE_URL={_mask_dsn(dsn)}")

    errors: list[str] = []
    try:
        with db_connection() as conn:
            print("连接: OK")
            for table in CORE_TABLES:
                try:
                    row = conn.execute(
                        f"SELECT COUNT(*) AS total FROM {table}"
                    ).fetchone()
                    total = int(row["total"]) if row else -1
                    print(f"  {table}: {total} 行")
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{table}: {exc}")
                    print(f"  {table}: 失败 ({exc})")

            probe_key = "verify:database_probe"
            conn.execute(
                "DELETE FROM app_metadata WHERE key = ?",
                (probe_key,),
            )
            conn.execute(
                "INSERT INTO app_metadata(key, value) VALUES (?, ?)",
                (probe_key, "ok"),
            )
            row = conn.execute(
                "SELECT value FROM app_metadata WHERE key = ?",
                (probe_key,),
            ).fetchone()
            conn.execute(
                "DELETE FROM app_metadata WHERE key = ?",
                (probe_key,),
            )
            conn.commit()
            if row and row["value"] == "ok":
                print("读写探针 (app_metadata): OK")
            else:
                errors.append("app_metadata 探针读写异常")
                print("读写探针 (app_metadata): 失败")
    except Exception as exc:  # noqa: BLE001
        print(f"连接: 失败 — {exc}")
        if is_postgres():
            print(
                "\n提示: Supabase Direct 在部分环境仅解析 IPv6，可改用 Session pooler 连接串，"
                "或在 Supabase 开启 IPv4 附加项。详见 docs/database-supabase-integration.md"
            )
        return 1

    if errors:
        print("\n部分检查未通过。")
        return 1
    print("\n数据库验证通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
