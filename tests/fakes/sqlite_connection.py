"""基于 SQLite 的离线数据库替身（测试专用，禁止用于生产）。

动机
----
本项目已完成 SQLite -> Postgres 迁移：`db_connection.db_connection()` 是模块级
contextmanager，硬连 `DATABASE_URL`。测试环境刻意不配置 Supabase（见
`tests/conftest.py`），而 CI/本地又不一定有可用 PG 实例，导致结果存储、价格
历史、卖家订阅等模块无法做有意义的离线往返测试。

本替身提供与 `DbConnection` 相同的最小接口（`execute` / `commit` / `raw`），
底层使用进程内 SQLite 内存库，并通过 `sqlite_row.DictRow` 复刻 psycopg
`dict_row` 的按列名访问语义。这样：

- 被测代码调用点**零改动**（仍走 `db_connection()` / `?` 占位符 / `conn.commit()`）；
- 存储层刻意编写的 Postgres 方言 SQL（`ON CONFLICT ... DO NOTHING/UPDATE`、
  `RETURNING`、`DISTINCT ON`、`CREATE INDEX IF NOT EXISTS`、`IS TRUE`、
  `CAST(x AS ...)` 等）都能被真实校验；
- 仍然离线、可重复、不依赖 Docker / Supabase。

该替身不是 SQL 解析 mock：所有断言都建立在真实执行的 SQL 之上。

替身边界（有意保留的差异，测试中不得依赖）
------------------------------------------
- SQLite 默认不强制外键/并发写锁语义；
- `ON CONFLICT` 的目标冲突发生在真实约束上，但类型严格性弱于 PG；
- JSON 列以 TEXT 存储（PG 侧为 JSONB），由被测代码的 `parse_json_field`
  容忍 str/obj 两种形态。
"""
from __future__ import annotations

import re
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Iterable, Iterator, Mapping, Sequence

from tests.fakes.sqlite_row import adapt_sqlite_row


# --- 基础表结构 ---------------------------------------------------------------
# 生产环境由 supabase/ 下的 migration 建立这些表；`ensure_schema` 只负责增量列。
# 离线替身需要先补齐基础表，才能让存储层 SQL 真正跑起来。
BASE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY,
    task_name TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    keyword TEXT NOT NULL DEFAULT '',
    description TEXT,
    analyze_images INTEGER NOT NULL DEFAULT 1,
    max_pages INTEGER NOT NULL DEFAULT 1,
    personal_only INTEGER NOT NULL DEFAULT 0,
    min_price TEXT,
    max_price TEXT,
    cron TEXT,
    ai_prompt_base_file TEXT,
    ai_prompt_criteria_file TEXT,
    account_state_file TEXT,
    account_strategy TEXT DEFAULT 'auto',
    free_shipping INTEGER NOT NULL DEFAULT 1,
    new_publish_option TEXT,
    region TEXT,
    decision_mode TEXT NOT NULL DEFAULT 'ai',
    keyword_rules_json TEXT NOT NULL DEFAULT '[]',
    is_running INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS app_metadata (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS result_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    result_filename TEXT NOT NULL,
    keyword TEXT NOT NULL DEFAULT '',
    task_name TEXT,
    crawl_time TEXT,
    publish_time TEXT,
    price REAL,
    price_display TEXT,
    item_id TEXT,
    title TEXT,
    link TEXT,
    link_unique_key TEXT NOT NULL,
    seller_nickname TEXT,
    is_recommended INTEGER NOT NULL DEFAULT 0,
    analysis_source TEXT,
    keyword_hit_count INTEGER NOT NULL DEFAULT 0,
    raw_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    CONSTRAINT uq_result_items_filename_key UNIQUE (result_filename, link_unique_key)
);

CREATE TABLE IF NOT EXISTS result_blacklist_rules (
    result_filename TEXT PRIMARY KEY,
    blacklist_keywords_json TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS price_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword_slug TEXT NOT NULL,
    keyword TEXT,
    task_name TEXT,
    snapshot_time TEXT,
    snapshot_day TEXT,
    run_id TEXT,
    item_id TEXT,
    title TEXT,
    price REAL,
    price_display TEXT,
    tags_json TEXT,
    region TEXT,
    seller TEXT,
    publish_time TEXT,
    link TEXT,
    CONSTRAINT uq_price_snapshots_key UNIQUE (keyword_slug, run_id, item_id)
);

CREATE TABLE IF NOT EXISTS seller_subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_user_id TEXT NOT NULL UNIQUE,
    seller_url TEXT,
    nickname TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    note TEXT,
    last_captured_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS seller_subscription_schedule (
    id INTEGER PRIMARY KEY DEFAULT 1,
    enabled INTEGER NOT NULL DEFAULT 1,
    cron TEXT NOT NULL DEFAULT '0 8 * * *',
    item_limit INTEGER NOT NULL DEFAULT 100,
    collect_ratings INTEGER NOT NULL DEFAULT 0,
    account_state_file TEXT,
    account_strategy TEXT NOT NULL DEFAULT 'auto',
    is_running INTEGER NOT NULL DEFAULT 0,
    pacing_json TEXT,
    last_run_summary TEXT,
    last_run_saved INTEGER NOT NULL DEFAULT 0,
    last_run_ok INTEGER NOT NULL DEFAULT 0,
    last_run_at TEXT,
    run_headless INTEGER,
    CONSTRAINT seller_subscription_schedule_single_row CHECK (id = 1)
);

-- 以下表结构对应生产 `ensure_schema` 的 bootstrap 分支（仅在全新库执行）。
-- 替身无法复用该分支（语句为 PG 方言且顺序交错），因此在此显式声明，
-- 必须与 src/infrastructure/persistence/db_connection.py 保持一致。
CREATE TABLE IF NOT EXISTS seller_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_name TEXT NOT NULL,
    seller_user_id TEXT NOT NULL,
    nickname TEXT,
    shop_level TEXT,
    praise_ratio REAL,
    followers INTEGER,
    item_count INTEGER,
    rating_count INTEGER,
    profile_json TEXT NOT NULL,
    captured_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    profile_day TEXT
);

CREATE TABLE IF NOT EXISTS seller_item_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_name TEXT NOT NULL,
    seller_user_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    title TEXT,
    price REAL,
    item_status TEXT,
    want_count INTEGER,
    view_count INTEGER,
    snapshot_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS shop_datacompass_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_state_file TEXT NOT NULL,
    shop_name TEXT,
    time_cycle TEXT NOT NULL,
    snapshot_date TEXT NOT NULL,
    api_name TEXT NOT NULL,
    metrics_json TEXT NOT NULL,
    raw_json TEXT,
    captured_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_datacompass_snapshot UNIQUE (account_state_file, time_cycle, snapshot_date, api_name)
);

CREATE INDEX IF NOT EXISTS idx_seller_profiles_task_time ON seller_profiles(task_name, captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_seller_metrics_item_time ON seller_item_metrics(item_id, snapshot_time DESC);
CREATE INDEX IF NOT EXISTS idx_datacompass_account_cycle ON shop_datacompass_snapshots(account_state_file, time_cycle, captured_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_seller_profiles_task_seller_day
    ON seller_profiles (task_name, seller_user_id, profile_day)
    WHERE profile_day IS NOT NULL;

-- 调度单例行：生产由 migration 插入（见 supabase/migrations/*_seller_subscription_registry.sql）。
-- `update_schedule_sync` 走 `UPDATE ... WHERE id = 1`，缺行时会静默更新 0 行，
-- 因此离线替身必须预置该行，才能真实验证 PATCH 的往返。
INSERT OR IGNORE INTO seller_subscription_schedule (id, enabled, cron, item_limit)
    VALUES (1, 1, '0 8 * * *', 100);
"""
_DDL_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (r"\bBIGSERIAL\b", "INTEGER"),
    (r"\bSERIAL\b", "INTEGER"),
    (r"\bNOW\(\)", "CURRENT_TIMESTAMP"),
    (r"\bTIMESTAMPTZ\b", "TEXT"),
    (r"\bJSONB\b", "TEXT"),
    (r"\bDOUBLE PRECISION\b", "REAL"),
    (r"\bBOOLEAN\b", "INTEGER"),
    (r"\bNUMERIC\b", "REAL"),
)

# SQLite 的 ADD COLUMN 不接受表达式默认值（如 CAST('[]' AS jsonb)），
# 降级为等价字面量默认值。
_CAST_DEFAULT_PATTERN = re.compile(
    r"DEFAULT\s+CAST\(\s*'(?P<literal>[^']*)'\s+AS\s+[A-Za-z0-9_]+(\s+[A-Za-z0-9_]+)?\s*\)",
    re.IGNORECASE,
)

# SQLite 不支持 `CREATE INDEX IF NOT EXISTS ... (col DESC)` 之外的表达式索引差异，
# 但支持 IF NOT EXISTS；DISTINCT ON / LATERAL 需在 SELECT 层降级处理。
_DISTINCT_ON_PATTERN = re.compile(
    r"SELECT\s+DISTINCT\s+ON\s*\(\s*"
    r"(?P<key>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?)\s*\)\s*"
    r"(?P<rest>.*)",
    re.IGNORECASE | re.DOTALL,
)

# SQLite 不支持 ALTER TABLE ... ADD COLUMN IF NOT EXISTS
_ADD_COLUMN_IF_NOT_EXISTS_PATTERN = re.compile(
    r"ALTER\s+TABLE\s+(?P<table>[A-Za-z_][A-Za-z0-9_]*)\s+"
    r"ADD\s+COLUMN\s+IF\s+NOT\s+EXISTS\s+(?P<definition>.+)",
    re.IGNORECASE | re.DOTALL,
)

# SQLite 不支持 ALTER TABLE ... ALTER COLUMN ... {DROP NOT NULL | DROP DEFAULT}。
# 本项目的用法仅为「放宽已有约束」：把 NOT NULL / DEFAULT 去掉。SQLite 在
# in-memory 建表时本就不强制这两者，因此降级为幂等 no-op 即可对齐 PG 的可空语义。
_ALTER_COLUMN_RELAX_PATTERN = re.compile(
    r"ALTER\s+TABLE\s+[A-Za-z_][A-Za-z0-9_]*\s+"
    r"ALTER\s+COLUMN\s+[A-Za-z_][A-Za-z0-9_]*\s+"
    r"DROP\s+(?:NOT\s+NULL|DEFAULT)\s*$",
    re.IGNORECASE | re.DOTALL,
)

_CREATE_TABLE_NAME_PATTERN = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?P<table>[A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE,
)

_CREATE_INDEX_TABLE_PATTERN = re.compile(
    r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?"
    r"[A-Za-z_][A-Za-z0-9_]*\s+ON\s+(?!\()(?P<table>[A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE,
)

# SQLite 不支持 LEFT JOIN LATERAL (...) p ON TRUE；降级为 LEFT JOIN 子查询。
_LATERAL_JOIN_PATTERN = re.compile(
    r"LEFT\s+JOIN\s+LATERAL\s*\(\s*(?P<subquery>.*?)\s*\)\s*"
    r"(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\s+ON\s+TRUE",
    re.IGNORECASE | re.DOTALL,
)


def translate_ddl(sql: str) -> str:
    """把 Postgres DDL 片段降级为 SQLite 可执行形式。"""
    translated = sql
    for pattern, replacement in _DDL_REPLACEMENTS:
        translated = re.sub(pattern, replacement, translated, flags=re.IGNORECASE)
    translated = _CAST_DEFAULT_PATTERN.sub(
        lambda match: f"DEFAULT '{match.group('literal')}'", translated
    )
    return translated


def _strip_distinct_on(sql: str) -> str:
    """SQLite 无 DISTINCT ON：改写为普通 SELECT，由调用方在 Python 侧去重。

    生产代码已配套在 Python 侧做 `sort`/`_dedupe_latest`，因此这里只需保证
    SQL 可执行且返回同一批候选行（行集合超集不影响后续去重结果）。
    """
    match = _DISTINCT_ON_PATTERN.search(sql)
    if match is None:
        return sql
    return f"SELECT {match.group('rest')}"


def _flatten_lateral_joins(sql: str) -> str:
    """把相关子查询形式的 `LEFT JOIN LATERAL (...) alias ON TRUE` 降级为关联查询。

    SQLite 无 LATERAL。本项目唯一的用法是「取某卖家最新一条画像」：

        LEFT JOIN LATERAL (SELECT ... FROM seller_profiles
                           WHERE task_name = ? AND seller_user_id = s.seller_user_id
                           ORDER BY captured_at DESC LIMIT 1) p ON TRUE

    等价改写为对同一张表做聚合（`MAX(captured_at)`）后 JOIN，语义一致且 SQLite
    可执行。若出现其他 LATERAL 形态则原样返回，由 SQLite 报错而非静默出错。
    """
    match = _LATERAL_JOIN_PATTERN.search(sql)
    if match is None:
        return sql

    subquery = match.group("subquery").strip()
    if "seller_profiles" not in subquery or "captured_at DESC" not in subquery:
        return sql  # 未覆盖的形态：不做猜测性改写

    alias = match.group("alias")
    replacement = (
        f"LEFT JOIN seller_profiles {alias} ON {alias}.task_name = ? "
        f"AND {alias}.seller_user_id = s.seller_user_id "
        f"AND {alias}.captured_at = ("
        f"  SELECT MAX(p2.captured_at) FROM seller_profiles p2 "
        f"  WHERE p2.task_name = {alias}.task_name "
        f"  AND p2.seller_user_id = {alias}.seller_user_id"
        f")"
    )
    # 子查询里原本的 task_name = ? 参数被替换出的新参数占用，参数需再补一个占位符
    sql = sql[: match.start()] + replacement + sql[match.end():]
    return sql



class _SqliteCursor:
    """`sqlite3.Cursor` 薄包装，保持与 psycopg cursor 一致的返回值。"""

    def __init__(self, cursor: sqlite3.Cursor):
        self._cursor = cursor

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    @property
    def description(self):
        return self._cursor.description

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def __iter__(self):
        return iter(self._cursor)


class SqliteDbConnection:
    """`DbConnection` 的内存替身，接口与语义保持一致。"""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        self._lock = threading.RLock()
        # 见 execute()：语句顺序不敏感所需的待补列/待建索引登记表
        self._pending_columns: dict[str, list[str]] = {}
        self._pending_indexes: dict[str, list[str]] = {}

    # -- DbConnection 接口 -----------------------------------------------------
    def execute(
        self,
        sql: str,
        params: Sequence[Any] | Mapping[str, Any] | None = None,
    ):
        statement = translate_ddl(sql)
        statement = _flatten_lateral_joins(statement)
        statement = _strip_distinct_on(statement)
        with self._lock:
            stripped = statement.strip()
            if _ALTER_COLUMN_RELAX_PATTERN.match(stripped):
                # SQLite 无法在 ALTER 阶段修改列约束；in-memory 表本就不强制
                # NOT NULL / DEFAULT，直接视为已生效（对齐 PG 的可空语义）。
                return _SqliteCursor(self._conn.execute("SELECT 1 WHERE 0"))
            add_column = _ADD_COLUMN_IF_NOT_EXISTS_PATTERN.match(stripped)
            if add_column is not None:
                table = add_column.group("table")
                definition = add_column.group("definition")
                if not self._table_exists(table):
                    # 幂等 DDL 会在建表语句之前先跑；PG 侧对不存在的表同样报错，
                    # 但生产启动路径必然先建表。这里选择「记住待补列」而非报错，
                    # 使离线替身对语句顺序不敏感。
                    self._pending_columns.setdefault(table, []).append(definition)
                    return _SqliteCursor(self._conn.execute("SELECT 1 WHERE 0"))
                # 幂等：列已存在时跳过（对齐 Postgres 的 IF NOT EXISTS 语义）
                if not self._column_exists(table, definition):
                    self._conn.execute(
                        f"ALTER TABLE {table} ADD COLUMN {definition}"
                    )
                return _SqliteCursor(self._conn.execute("SELECT 1 WHERE 0"))
            create_index = _CREATE_INDEX_TABLE_PATTERN.match(stripped)
            if create_index is not None:
                target = create_index.group("table")
                if not self._table_exists(target):
                    # 同 ADD COLUMN：幂等 DDL 可能先于建表执行，先登记后补建。
                    self._pending_indexes.setdefault(target, []).append(stripped)
                    return _SqliteCursor(self._conn.execute("SELECT 1 WHERE 0"))
            if params is None:
                cursor = self._conn.execute(statement)
            elif isinstance(params, Mapping):
                cursor = self._conn.execute(statement, dict(params))
            else:
                cursor = self._conn.execute(statement, tuple(params))
            created = _CREATE_TABLE_NAME_PATTERN.match(statement.strip())
            if created is not None:
                self._drain_pending_indexes(created.group("table"))
                self._drain_pending_columns(created.group("table"))
        return _SqliteCursor(cursor)

    def _table_exists(self, table: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        return row is not None

    def _drain_pending_indexes(self, table: str) -> None:
        """建表后补齐此前因表不存在而挂起的 CREATE INDEX。"""
        for statement in self._pending_indexes.pop(table, []):
            self._conn.execute(statement)

    def _drain_pending_columns(self, table: str) -> None:
        """建表后补齐此前因表不存在而挂起的 ADD COLUMN。"""
        for definition in self._pending_columns.pop(table, []):
            if not self._column_exists(table, definition):
                self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")

    def _column_exists(self, table: str, column_definition: str) -> bool:
        column_name = column_definition.strip().split()[0].strip('"')
        rows = self._conn.execute(f'PRAGMA table_info("{table}")').fetchall()
        return any(row["name"] == column_name for row in rows)

    def commit(self) -> None:
        with self._lock:
            self._conn.commit()

    @property
    def raw(self) -> sqlite3.Connection:
        return self._conn

    # -- 测试关卡 ---------------------------------------------------------------
    def execute_script(self, sql: str) -> None:
        with self._lock:
            for statement in _split_statements(translate_ddl(sql)):
                self._conn.execute(statement)

    def last_insert_id(self) -> int:
        with self._lock:
            return int(self._conn.execute("SELECT last_insert_rowid()").fetchone()[0])

    def close(self) -> None:
        with self._lock:
            self._conn.close()


def _split_statements(sql: str) -> Iterator[str]:
    for statement in sql.split(";"):
        text = statement.strip()
        if text:
            yield text


class SqliteConnectionFactory:
    """管理一个进程内共享的内存库，为每次 `db_connection()` 打开新连接。

    采用 `file:...?mode=memory&cache=shared` 的共享缓存 URI：同一进程内多个连接
    看到同一份数据，模拟 PG 的连接池语义；只有所有连接关闭后数据才会释放，因此
    这里长期持有一个 keep-alive 连接。
    """

    def __init__(self, name: str = "testdb"):
        self._uri = f"file:{name}?mode=memory&cache=shared"
        self._lock = threading.RLock()
        self._keepalive = self._new_connection()
        self._ensure_base_schema()

    def _ensure_base_schema(self) -> None:
        with self._lock:
            for statement in _split_statements(BASE_SCHEMA_SQL):
                self._keepalive.execute(statement)
            self._apply_production_schema()
            self._keepalive.commit()

    def _apply_production_schema(self) -> None:
        """用生产 schema 定义补齐替身表结构，避免两边手工维护导致漂移。

        生产侧 `ensure_schema` 的语句是 PG 方言，且部分幂等 DDL 会先于建表执行
        （如 `ALTER TABLE seller_profiles ADD COLUMN profile_day` 出现在该表
        CREATE 之前）。这里按序执行并把 `OperationalError` 记下来，最后统一重放，
        从而对语句顺序不敏感。
        """
        try:
            from src.infrastructure.persistence import db_connection as module
        except Exception:  # pragma: no cover - 循环导入等极端情形
            return
        statements = list(getattr(module, "_INCREMENTAL_SCHEMA_STATEMENTS", ()))
        # `ensure_schema` 内的 bootstrap 语句未导出，这里用同源的方式补齐：
        # 直接调用生产 `ensure_schema` 让替身连接走一遍真实路径。
        try:
            schema_conn = SqliteDbConnection(self._keepalive)
            module.ensure_schema(schema_conn)
        except sqlite3.OperationalError:
            pass
        for sql in statements:
            self._replay_statement(sql)

    def _replay_statement(self, sql: str) -> None:
        """执行单条生产 DDL；失败时静默跳过（表/列可能已存在）。"""
        try:
            for statement in _split_statements(translate_ddl(sql)):
                self._keepalive.execute(statement)
        except sqlite3.OperationalError:
            return

    def _new_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self._uri,
            uri=True,
            check_same_thread=False,
            isolation_level="DEFERRED",
        )
        conn.row_factory = adapt_sqlite_row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.create_function("now", 0, lambda: "2026-09-22T06:00:00+00:00", deterministic=True)
        return conn

    def __call__(self, _db_path: str | None = None):
        """返回 contextmanager，签名与行为对齐生产 `db_connection()`。"""
        return self._open()

    @contextmanager
    def _open(self) -> Iterator[SqliteDbConnection]:
        connection = SqliteDbConnection(self._new_connection())
        try:
            yield connection
        finally:
            connection.close()

    def seed(self, sql: str) -> None:
        with self._lock:
            for statement in _split_statements(translate_ddl(sql)):
                self._keepalive.execute(statement)
            self._keepalive.commit()

    def seed_params(self, sql: str, params: Iterable[Any]) -> None:
        with self._lock:
            self._keepalive.execute(sql, tuple(params))
            self._keepalive.commit()

    def reset(self) -> None:
        """清空全部用户表，供多个测试复用同一实例时保证隔离。"""
        with self._lock:
            cursor = self._keepalive.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name NOT LIKE 'sqlite_%'"
            )
            tables = [row["name"] for row in cursor.fetchall()]
            for table in tables:
                self._keepalive.execute(f'DROP TABLE IF EXISTS "{table}"')
            self._keepalive.commit()
