"""
统一数据库连接（SQLite / Postgres）。
"""
from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterator, Mapping, Sequence

from src.infrastructure.persistence.database_config import (
    get_database_driver,
    get_postgres_dsn,
    get_sqlite_database_path,
    is_postgres,
)
from src.infrastructure.persistence.sqlite_connection import (
    _apply_pragmas,
    _prepare_database_file,
    init_schema,
)


_NAMED_PARAM_PATTERN = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)")


class DbConnection:
    """对 sqlite3 / psycopg 连接的薄封装，统一占位符与返回行格式。"""

    def __init__(self, conn: Any, *, driver: str):
        self._conn = conn
        self._driver = driver

    def execute(
        self,
        sql: str,
        params: Sequence[Any] | Mapping[str, Any] | None = None,
    ):
        sql = self._adapt_sql(sql)
        if params is None:
            return self._conn.execute(sql)
        if isinstance(params, Mapping):
            adapted = self._adapt_mapping_params(params)
            return self._conn.execute(sql, adapted)
        adapted = tuple(params)
        return self._conn.execute(sql, adapted)

    def commit(self) -> None:
        self._conn.commit()

    @property
    def raw(self) -> Any:
        return self._conn

    def _adapt_sql(self, sql: str) -> str:
        if self._driver != "postgres":
            return sql
        if "?" in sql:
            sql = sql.replace("?", "%s")
        if _NAMED_PARAM_PATTERN.search(sql):

            def _replace(match: re.Match[str]) -> str:
                return f"%({match.group(1)})s"

            sql = _NAMED_PARAM_PATTERN.sub(_replace, sql)
        return sql

    def _adapt_mapping_params(self, params: Mapping[str, Any]) -> dict[str, Any]:
        return dict(params)


@contextmanager
def db_connection(db_path: str | None = None) -> Iterator[DbConnection]:
    driver = get_database_driver()
    if driver == "postgres":
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(get_postgres_dsn(), row_factory=dict_row) as conn:
            yield DbConnection(conn, driver="postgres")
    else:
        path = db_path or get_sqlite_database_path()
        _prepare_database_file(path)
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        try:
            _apply_pragmas(conn)
            yield DbConnection(conn, driver="sqlite")
        finally:
            conn.close()


# 兼容旧 import 名称
sqlite_connection = db_connection


def ensure_schema(conn: DbConnection) -> None:
    if is_postgres():
        return
    init_schema(conn.raw)
