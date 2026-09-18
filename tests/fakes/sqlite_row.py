"""SQLite 行对象适配为 Postgres/psycopg 的 dict 行语义。

生产代码（`db_connection.DbConnection` + `psycopg.rows.dict_row`）统一通过
`row["column"]` 取值。sqlite3 默认返回 tuple，因此这里提供一个只按列名取值的
薄适配，让底层存储代码无需感知测试替身。
"""
from __future__ import annotations

import sqlite3
from typing import Any, Iterator, Mapping


class DictRow(Mapping[str, Any]):
    """只支持按列名访问的行，兼容 `dict(row)` / `row["col"]` / `.get()`。

    SQLite 无原生 BOOLEAN，`0/1` 会以 int 返回，而 psycopg 返回 bool。这里按列名
    推断布尔列并归一化，避免生产代码 `is False` 之类的判断在替身上失真。
    """

    __slots__ = ("_keys", "_values", "_index")

    def __init__(self, keys: tuple[str, ...], values: tuple[Any, ...]):
        self._keys = keys
        self._values = tuple(
            _coerce_boolean(key, value) for key, value in zip(keys, values)
        )
        self._index = {key: position for position, key in enumerate(keys)}

    def __getitem__(self, key: Any) -> Any:
        if not isinstance(key, str):
            return self._values[key]
        try:
            return self._values[self._index[key]]
        except KeyError:
            raise KeyError(key) from None

    def get(self, key: str, default: Any = None) -> Any:
        position = self._index.get(key)
        if position is None:
            return default
        return self._values[position]

    def keys(self):
        return self._keys

    def values(self):
        return self._values

    def items(self):
        return zip(self._keys, self._values)

    def __iter__(self) -> Iterator[str]:
        return iter(self._keys)

    def __len__(self) -> int:
        return len(self._keys)

    def __contains__(self, key: object) -> bool:
        return key in self._index

    def __repr__(self) -> str:  # pragma: no cover - 调试辅助
        return f"DictRow({dict(self.items())})"


def adapt_sqlite_row(cursor: sqlite3.Cursor, row: tuple[Any, ...]) -> DictRow:
    keys = tuple(description[0] for description in (cursor.description or ()))
    return DictRow(keys, row)


# 与 Postgres schema 中 BOOLEAN 列对应的列名（含 `is_` / `enabled` 等直白命名）。
_BOOLEAN_COLUMNS = frozenset(
    {
        "enabled",
        "analyze_images",
        "personal_only",
        "free_shipping",
        "is_running",
        "collect_ratings",
        "is_recommended",
        "in_stock",
    }
)


def _coerce_boolean(key: str, value: Any) -> Any:
    """SQLite 用 0/1 存布尔；归一化为 bool 以对齐 psycopg 的行语义。"""
    if value is None or not isinstance(value, int) or isinstance(value, bool):
        return value
    if key in _BOOLEAN_COLUMNS or key.startswith("is_"):
        return bool(value)
    return value

