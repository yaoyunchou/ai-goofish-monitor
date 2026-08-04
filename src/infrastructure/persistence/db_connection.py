"""
PostgreSQL 数据库连接。
"""
from __future__ import annotations

import re
from contextlib import contextmanager
from typing import Any, Iterator, Mapping, Sequence

from src.infrastructure.persistence.database_config import get_postgres_dsn

_NAMED_PARAM_PATTERN = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)")


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
    """Schema 由 Supabase migration 管理，运行时无需建表。"""
    del conn
