"""统一数据库连接（Postgres / psycopg）。"""
from __future__ import annotations

import re
from contextlib import contextmanager
from typing import Any, Iterator, Mapping, Sequence

from src.infrastructure.persistence.database_config import get_postgres_dsn

_NAMED_PARAM_PATTERN = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)")


class DbConnection:
    """对 psycopg 连接的薄封装，统一占位符与返回行格式。

    业务层仍用 ``?`` / ``:name`` 占位符书写 SQL，由本类在执行前转换为 psycopg 的
    ``%s`` / ``%(name)s`` 形式，从而保持仓储代码与具体驱动解耦。
    """

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
            sql = _NAMED_PARAM_PATTERN.sub(lambda m: f"%({m.group(1)})s", sql)
        return sql


@contextmanager
def db_connection() -> Iterator[DbConnection]:
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(get_postgres_dsn(), row_factory=dict_row) as conn:
        yield DbConnection(conn)


def ensure_schema(conn: DbConnection) -> None:
    """Postgres schema 由 supabase migration 维护，应用侧不自动建表。

    首次部署需手动执行 ``supabase/migrations/20260803120000_initial_goofish_schema.sql``，
    或通过 ``supabase db push`` 应用。可用 ``python -m scripts.verify_database`` 自检。
    """
    return None
