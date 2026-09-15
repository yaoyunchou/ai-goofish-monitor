"""
PostgreSQL 数据库连接。
"""
from __future__ import annotations

import re
from contextlib import contextmanager
from typing import Any, Iterator, Mapping, Sequence

from src.infrastructure.persistence.database_config import get_postgres_dsn

# 不匹配 PostgreSQL 类型转换（如 '[]'::jsonb），只替换 :name 命名参数
_NAMED_PARAM_PATTERN = re.compile(r"(?<!:):([A-Za-z_][A-Za-z0-9_]*)")


class DbConnection:
    """对 psycopg 连接的薄封装，统一 `?` 占位符与 dict 行。"""

    def __init__(self, conn: Any):
        self._conn = conn

    def execute(
        self,
        sql: str,
        params: Sequence[Any] | Mapping[str, Any] | None = None,
    ):
        sql = self._adapt_sql(sql)
        if params is None:
            return self._conn.execute(sql)
        if isinstance(params, Mapping):
            return self._conn.execute(sql, dict(params))
        return self._conn.execute(sql, tuple(params))

    def commit(self) -> None:
        self._conn.commit()

    @property
    def raw(self) -> Any:
        return self._conn

    def _adapt_sql(self, sql: str) -> str:
        if "?" in sql:
            sql = sql.replace("?", "%s")
        if _NAMED_PARAM_PATTERN.search(sql):

            def _replace(match: re.Match[str]) -> str:
                return f"%({match.group(1)})s"

            sql = _NAMED_PARAM_PATTERN.sub(_replace, sql)
        return sql


@contextmanager
def db_connection(db_path: str | None = None) -> Iterator[DbConnection]:
    del db_path  # 仅 Postgres；保留参数兼容旧调用
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(get_postgres_dsn(), row_factory=dict_row) as conn:
        yield DbConnection(conn)


def ensure_schema(conn: DbConnection) -> None:
    """应用增量 schema（兼容尚未手动跑 migration 的数据库）。"""
    statements = [
        "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS task_type TEXT NOT NULL DEFAULT 'keyword_search'",
        "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS seller_user_ids_json JSONB NOT NULL DEFAULT CAST('[]' AS jsonb)",
        "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS seller_urls_json JSONB NOT NULL DEFAULT CAST('[]' AS jsonb)",
        "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS collect_ratings BOOLEAN NOT NULL DEFAULT FALSE",
        """
        CREATE TABLE IF NOT EXISTS seller_profiles (
            id BIGSERIAL PRIMARY KEY,
            task_name TEXT NOT NULL,
            seller_user_id TEXT NOT NULL,
            nickname TEXT,
            shop_level TEXT,
            praise_ratio NUMERIC,
            followers INTEGER,
            item_count INTEGER,
            rating_count INTEGER,
            profile_json JSONB NOT NULL,
            captured_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_seller_profiles_task_time ON seller_profiles(task_name, captured_at DESC)",
        """
        CREATE TABLE IF NOT EXISTS seller_item_metrics (
            id BIGSERIAL PRIMARY KEY,
            task_name TEXT NOT NULL,
            seller_user_id TEXT NOT NULL,
            item_id TEXT NOT NULL,
            title TEXT,
            price DOUBLE PRECISION,
            item_status TEXT,
            want_count INTEGER,
            view_count INTEGER,
            snapshot_time TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_seller_metrics_item_time ON seller_item_metrics(item_id, snapshot_time DESC)",
        """
        CREATE TABLE IF NOT EXISTS shop_datacompass_snapshots (
            id BIGSERIAL PRIMARY KEY,
            account_state_file TEXT NOT NULL,
            shop_name TEXT,
            time_cycle TEXT NOT NULL,
            snapshot_date DATE NOT NULL,
            api_name TEXT NOT NULL,
            metrics_json JSONB NOT NULL,
            raw_json JSONB,
            captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_datacompass_snapshot UNIQUE (account_state_file, time_cycle, snapshot_date, api_name)
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_datacompass_account_cycle ON shop_datacompass_snapshots(account_state_file, time_cycle, captured_at DESC)",
        """
        CREATE TABLE IF NOT EXISTS seller_subscriptions (
            id BIGSERIAL PRIMARY KEY,
            seller_user_id TEXT NOT NULL UNIQUE,
            seller_url TEXT,
            nickname TEXT,
            enabled BOOLEAN NOT NULL DEFAULT TRUE,
            note TEXT,
            last_captured_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS seller_subscription_schedule (
            id INT PRIMARY KEY DEFAULT 1,
            enabled BOOLEAN NOT NULL DEFAULT TRUE,
            cron TEXT NOT NULL DEFAULT '0 8 * * *',
            item_limit INT NOT NULL DEFAULT 100,
            collect_ratings BOOLEAN NOT NULL DEFAULT FALSE,
            account_state_file TEXT,
            account_strategy TEXT NOT NULL DEFAULT 'auto',
            is_running BOOLEAN NOT NULL DEFAULT FALSE,
            pacing_json JSONB,
            CONSTRAINT seller_subscription_schedule_single_row CHECK (id = 1)
        )
        """,
        """
        ALTER TABLE seller_subscription_schedule
            ADD COLUMN IF NOT EXISTS pacing_json JSONB
        """,
        """
        ALTER TABLE seller_subscription_schedule
            ADD COLUMN IF NOT EXISTS last_run_summary TEXT
        """,
        """
        ALTER TABLE seller_subscription_schedule
            ADD COLUMN IF NOT EXISTS last_run_saved INT NOT NULL DEFAULT 0
        """,
        """
        ALTER TABLE seller_subscription_schedule
            ADD COLUMN IF NOT EXISTS last_run_ok BOOLEAN NOT NULL DEFAULT FALSE
        """,
        """
        ALTER TABLE seller_subscription_schedule
            ADD COLUMN IF NOT EXISTS last_run_at TIMESTAMPTZ
        """,
        """
        INSERT INTO seller_subscription_schedule (id, enabled, cron, item_limit)
        VALUES (1, TRUE, '0 8 * * *', 100)
        ON CONFLICT (id) DO NOTHING
        """,
    ]
    for sql in statements:
        conn.execute(sql)
    conn.commit()
