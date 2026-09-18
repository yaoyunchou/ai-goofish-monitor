"""
PostgreSQL 数据库连接。
"""
from __future__ import annotations

import re
from contextlib import contextmanager
from typing import Any, Iterator, Mapping, Sequence

from src.infrastructure.persistence.database_config import get_postgres_dsn
from src.infrastructure.persistence.sql_dialect import upsert_app_metadata_sql

SCHEMA_BOOTSTRAP_KEY = "bootstrap:schema_goofish_v2"

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


def _postgres_connect_kwargs() -> dict[str, Any]:
    return {
        "connect_timeout": 10,
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 3,
    }


@contextmanager
def db_connection(db_path: str | None = None) -> Iterator[DbConnection]:
    del db_path  # 仅 Postgres；保留参数兼容旧调用
    import psycopg
    from psycopg.rows import dict_row

    dsn = get_postgres_dsn()
    kwargs = _postgres_connect_kwargs()
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            with psycopg.connect(dsn, row_factory=dict_row, **kwargs) as conn:
                conn.execute("SET TIME ZONE 'Asia/Shanghai'")
                yield DbConnection(conn)
                return
        except psycopg.OperationalError as exc:
            last_error = exc
            if attempt == 0:
                continue
            raise
    if last_error is not None:
        raise last_error


def _schema_bootstrap_completed(conn: DbConnection) -> bool:
    row = conn.execute(
        "SELECT value FROM app_metadata WHERE key = ?",
        (SCHEMA_BOOTSTRAP_KEY,),
    ).fetchone()
    return row is not None


def _schema_already_present(conn: DbConnection) -> bool:
    """已跑过 Supabase migration 或历史 ensure_schema 的库，避免重复 DDL 抢锁。"""
    try:
        conn.execute(
            """
            SELECT run_headless
            FROM seller_subscription_schedule
            WHERE id = 1
            """
        ).fetchone()
        conn.execute("SELECT 1 FROM seller_subscriptions LIMIT 1")
        return True
    except Exception:
        return False


# 幂等 DDL：每次启动都执行，供已上线库补齐新表/新列（不依赖 bootstrap 标记）
_INCREMENTAL_SCHEMA_STATEMENTS = [
    """
    ALTER TABLE seller_subscription_schedule
        ADD COLUMN IF NOT EXISTS run_headless BOOLEAN NOT NULL DEFAULT FALSE
    """,
    """
    ALTER TABLE seller_subscription_schedule
        ALTER COLUMN run_headless DROP NOT NULL
    """,
    """
    ALTER TABLE seller_subscription_schedule
        ALTER COLUMN run_headless DROP DEFAULT
    """,
    """
    CREATE TABLE IF NOT EXISTS item_detail_api_raw (
        id BIGSERIAL PRIMARY KEY,
        item_id TEXT NOT NULL,
        seller_user_id TEXT,
        task_name TEXT NOT NULL,
        source TEXT NOT NULL DEFAULT 'seller_subscription',
        api_name TEXT NOT NULL DEFAULT 'mtop.taobao.idle.pc.detail',
        raw_json JSONB NOT NULL,
        captured_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_item_detail_api_raw_item_time ON item_detail_api_raw(item_id, captured_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_item_detail_api_raw_task_item_time ON item_detail_api_raw(task_name, item_id, captured_at DESC)",
    """
    CREATE TABLE IF NOT EXISTS crawl_raw_records (
        id BIGSERIAL PRIMARY KEY,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        raw_json JSONB NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS seller_subscription_items (
        task_name TEXT NOT NULL,
        seller_user_id TEXT NOT NULL,
        item_id TEXT NOT NULL,
        title TEXT,
        price DOUBLE PRECISION,
        item_status TEXT,
        item_link TEXT,
        main_image TEXT,
        first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (task_name, seller_user_id, item_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_seller_subscription_items_seller ON seller_subscription_items (seller_user_id, last_seen_at DESC)",
    """
    CREATE TABLE IF NOT EXISTS seller_item_daily_metrics (
        id BIGSERIAL PRIMARY KEY,
        task_name TEXT NOT NULL,
        seller_user_id TEXT NOT NULL,
        item_id TEXT NOT NULL,
        snapshot_day DATE NOT NULL,
        want_count INTEGER,
        view_count INTEGER,
        captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        raw_record_id BIGINT NOT NULL REFERENCES crawl_raw_records(id) ON DELETE CASCADE,
        CONSTRAINT uq_seller_item_daily_metrics_day
            UNIQUE (task_name, seller_user_id, item_id, snapshot_day),
        CONSTRAINT uq_seller_item_daily_metrics_raw
            UNIQUE (raw_record_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_seller_item_daily_metrics_item_day ON seller_item_daily_metrics (item_id, snapshot_day DESC)",
    "CREATE INDEX IF NOT EXISTS idx_seller_item_daily_metrics_task_day ON seller_item_daily_metrics (task_name, snapshot_day DESC)",
    "CREATE INDEX IF NOT EXISTS idx_seller_item_daily_metrics_task_day_seller ON seller_item_daily_metrics (task_name, snapshot_day, seller_user_id)",
    "ALTER TABLE seller_profiles ADD COLUMN IF NOT EXISTS profile_day DATE",
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_seller_profiles_task_seller_day
        ON seller_profiles (task_name, seller_user_id, profile_day)
        WHERE profile_day IS NOT NULL
    """,
    # --- 商品级监控健康度自动停用 ---
    "ALTER TABLE seller_subscription_items ADD COLUMN IF NOT EXISTS is_muted BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE seller_subscription_items ADD COLUMN IF NOT EXISTS muted_at TIMESTAMPTZ",
    "ALTER TABLE seller_subscription_items ADD COLUMN IF NOT EXISTS muted_reason TEXT",
    "ALTER TABLE seller_subscription_items ADD COLUMN IF NOT EXISTS muted_week DATE",
    "CREATE INDEX IF NOT EXISTS idx_seller_subscription_items_muted ON seller_subscription_items (seller_user_id, is_muted)",
    """
    CREATE TABLE IF NOT EXISTS item_monitor_health_weekly (
        id             BIGSERIAL PRIMARY KEY,
        week_start     DATE NOT NULL,
        week_end       DATE NOT NULL,
        seller_user_id TEXT NOT NULL,
        item_id        TEXT NOT NULL,
        title          TEXT,
        days_with_data INT,
        view_start     INTEGER,
        view_end       INTEGER,
        view_growth    INTEGER,
        want_start     INTEGER,
        want_end       INTEGER,
        want_growth    INTEGER,
        healthy        BOOLEAN NOT NULL,
        reason         TEXT,
        action         TEXT NOT NULL,
        decided_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT uq_item_monitor_health_week
            UNIQUE (week_start, seller_user_id, item_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_item_monitor_health_week ON item_monitor_health_weekly (week_start DESC, action)",
    "CREATE INDEX IF NOT EXISTS idx_item_monitor_health_item ON item_monitor_health_weekly (seller_user_id, item_id, week_start DESC)",
]


def ensure_incremental_schema(conn: DbConnection) -> None:
    """对已存在的数据库补齐后续 migration（CREATE IF NOT EXISTS / ADD COLUMN IF NOT EXISTS）。"""
    for sql in _INCREMENTAL_SCHEMA_STATEMENTS:
        conn.execute(sql)
    conn.commit()


def ensure_schema(conn: DbConnection) -> None:
    """应用增量 schema（兼容尚未手动跑 migration 的数据库）。"""
    ensure_incremental_schema(conn)
    if _schema_bootstrap_completed(conn):
        return
    if _schema_already_present(conn):
        conn.execute(upsert_app_metadata_sql(), (SCHEMA_BOOTSTRAP_KEY, "done"))
        conn.commit()
        return

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
        ALTER TABLE seller_subscription_schedule
            ADD COLUMN IF NOT EXISTS run_headless BOOLEAN NOT NULL DEFAULT FALSE
        """,
        """
        INSERT INTO seller_subscription_schedule (id, enabled, cron, item_limit)
        VALUES (1, TRUE, '0 8 * * *', 100)
        ON CONFLICT (id) DO NOTHING
        """,
    ]
    for sql in statements:
        conn.execute(sql)
    conn.execute(upsert_app_metadata_sql(), (SCHEMA_BOOTSTRAP_KEY, "done"))
    conn.commit()
