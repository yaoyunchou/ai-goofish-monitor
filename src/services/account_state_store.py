"""统一账号登录态存取：优先数据库，兼容文件。"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.infrastructure.persistence.db_connection import db_connection
from src.infrastructure.persistence.storage_bootstrap import bootstrap_storage
from src.utils import log_time

STATE_DIR = os.getenv("ACCOUNT_STATE_DIR", "state") or "state"


def _strip_quotes(value: str) -> str:
    if not value:
        return value
    if value.startswith(('"', "'")) and value.endswith(('"', "'")):
        return value[1:-1]
    return value


def _state_dir() -> str:
    return _strip_quotes((STATE_DIR or "state").strip())


def _file_path(name: str) -> str:
    return os.path.join(_state_dir(), f"{name}.json")


def _is_file_path(value: str) -> bool:
    """判断字符串是文件路径还是纯账号名。"""
    return value.endswith(".json") or "/" in value or "\\" in value


def _name_from_path(value: str) -> str:
    base = os.path.basename(value)
    if base.endswith(".json"):
        return base[:-5]
    return base


# ---- DB 操作 ----

def _db_get(name: str) -> Optional[dict]:
    bootstrap_storage()
    with db_connection() as conn:
        row = conn.execute(
            "SELECT content_json FROM xianyu_account_states WHERE name = %s",
            (name,),
        ).fetchone()
        if row is None:
            return None
        raw = row["content_json"] if isinstance(row, dict) else row[0]
        if isinstance(raw, str):
            return json.loads(raw)
        return raw


def _db_list_names() -> List[str]:
    bootstrap_storage()
    with db_connection() as conn:
        rows = conn.execute(
            "SELECT name FROM xianyu_account_states ORDER BY name"
        ).fetchall()
        return [r["name"] if isinstance(r, dict) else r[0] for r in rows]


def _db_upsert(name: str, content: dict, note: Optional[str] = None) -> None:
    bootstrap_storage()
    now = datetime.now().isoformat()
    with db_connection() as conn:
        conn.execute(
            """
            INSERT INTO xianyu_account_states (name, content_json, updated_at, note)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (name) DO UPDATE SET
                content_json = EXCLUDED.content_json,
                updated_at = EXCLUDED.updated_at,
                note = EXCLUDED.note
            """,
            (name, json.dumps(content, ensure_ascii=False), now, note),
        )
        conn.commit()


def _db_delete(name: str) -> bool:
    bootstrap_storage()
    with db_connection() as conn:
        cur = conn.execute(
            "DELETE FROM xianyu_account_states WHERE name = %s", (name,)
        )
        conn.commit()
        return cur.rowcount > 0


# ---- 文件操作（兼容） ----

def _file_get(path: str) -> Optional[dict]:
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _file_list() -> List[str]:
    d = _state_dir()
    if not os.path.isdir(d):
        return []
    return sorted(
        f[:-5] for f in os.listdir(d) if f.endswith(".json")
    )


def _file_write(path: str, content: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(content, f, ensure_ascii=False, indent=2)


# ---- 公共 API ----

def get_account_state(name_or_path: str) -> Optional[dict]:
    """按账号名或文件路径取登录态，优先 DB，找不到再读文件。"""
    if _is_file_path(name_or_path):
        name = _name_from_path(name_or_path)
        path = name_or_path if os.path.isabs(name_or_path) or "/" in name_or_path or "\\" in name_or_path else _file_path(name)
    else:
        name = name_or_path
        path = _file_path(name)

    state = _db_get(name)
    if state is not None:
        log_time(f"[账号态] DB 命中 name={name}")
        return state

    state = _file_get(path)
    if state is not None:
        log_time(f"[账号态] 文件命中 path={path}，自动导入 DB")
        try:
            _db_upsert(name, state)
        except Exception as exc:
            log_time(f"[账号态] 自动导入 DB 失败（不影响运行）: {exc}")
        return state

    log_time(f"[账号态] 未找到 name={name} path={path}")
    return None


def list_account_names() -> List[str]:
    """列出所有可用账号名（DB + 文件去重）。"""
    names = set(_db_list_names())
    names.update(_file_list())
    return sorted(names)


def save_account_state(name: str, content: dict, *, write_file: bool = True) -> None:
    """保存登录态到 DB，可选同时写文件（兼容旧爬虫）。"""
    _db_upsert(name, content)
    if write_file:
        _file_write(_file_path(name), content)
    log_time(f"[账号态] 已保存 name={name} (db+file={write_file})")


def delete_account_state(name: str) -> bool:
    """从 DB 和文件都删除。"""
    deleted = _db_delete(name)
    path = _file_path(name)
    if os.path.isfile(path):
        os.remove(path)
        deleted = True
    return deleted


def resolve_for_playwright(name_or_path: str) -> Tuple[dict, str]:
    """返回 (state_dict, source) 供 Playwright storage_state 使用。"""
    state = get_account_state(name_or_path)
    if state is None:
        raise FileNotFoundError(f"登录态不存在: {name_or_path}")
    return state, "db"


def import_all_from_files() -> int:
    """把 state/*.json 批量导入 DB，返回导入数量。"""
    names = _file_list()
    count = 0
    for name in names:
        state = _file_get(_file_path(name))
        if state is not None:
            _db_upsert(name, state)
            count += 1
    log_time(f"[账号态] 从文件导入 {count} 个账号到 DB")
    return count
