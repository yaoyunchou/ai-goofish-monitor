"""
从 config.json 将缺失任务合并进数据库（按 task_name 去重）。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.infrastructure.persistence.db_connection import DbConnection
from src.infrastructure.persistence.sql_dialect import as_sql_bool, json_text


def _load_config_tasks(config_path: Path) -> list[dict[str, Any]]:
    if not config_path.exists():
        return []
    content = config_path.read_text(encoding="utf-8").strip()
    if not content:
        return []
    data = json.loads(content)
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def _existing_task_names(conn: DbConnection) -> set[str]:
    rows = conn.execute("SELECT task_name FROM tasks").fetchall()
    names: set[str] = set()
    for row in rows:
        name = row["task_name"] if isinstance(row, dict) else row[0]
        if name:
            names.add(str(name))
    return names


def _next_task_id(conn: DbConnection) -> int:
    row = conn.execute("SELECT COALESCE(MAX(id), -1) AS max_id FROM tasks").fetchone()
    max_id = row["max_id"] if isinstance(row, dict) else row[0]
    return int(max_id) + 1


def _insert_task_row(conn: DbConnection, task_id: int, raw_task: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO tasks (
            id, task_name, enabled, keyword, description, analyze_images,
            max_pages, personal_only, min_price, max_price, cron,
            ai_prompt_base_file, ai_prompt_criteria_file, account_state_file,
            account_strategy, free_shipping, new_publish_option, region,
            decision_mode, keyword_rules_json, is_running
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            task_id,
            raw_task.get("task_name", ""),
            as_sql_bool(raw_task.get("enabled", True)),
            raw_task.get("keyword", ""),
            raw_task.get("description", ""),
            as_sql_bool(raw_task.get("analyze_images", True)),
            int(raw_task.get("max_pages", 1) or 1),
            as_sql_bool(raw_task.get("personal_only", False)),
            raw_task.get("min_price"),
            raw_task.get("max_price"),
            raw_task.get("cron"),
            raw_task.get("ai_prompt_base_file", "prompts/base_prompt.txt"),
            raw_task.get("ai_prompt_criteria_file", ""),
            raw_task.get("account_state_file"),
            raw_task.get("account_strategy", "auto"),
            as_sql_bool(raw_task.get("free_shipping", True)),
            raw_task.get("new_publish_option"),
            raw_task.get("region"),
            raw_task.get("decision_mode", "ai"),
            json_text(raw_task.get("keyword_rules") or []),
            as_sql_bool(raw_task.get("is_running", False)),
        ),
    )


def sync_missing_tasks_from_config(
    conn: DbConnection,
    legacy_config_file: str | None,
) -> list[str]:
    """
    将 config.json 中尚未入库的任务按 task_name 插入。
    返回新插入的任务名称列表。
    """
    if not legacy_config_file:
        return []
    config_tasks = _load_config_tasks(Path(legacy_config_file))
    if not config_tasks:
        return []

    existing = _existing_task_names(conn)
    inserted: list[str] = []
    for raw_task in config_tasks:
        task_name = str(raw_task.get("task_name") or "").strip()
        if not task_name or task_name in existing:
            continue
        task_id = _next_task_id(conn)
        _insert_task_row(conn, task_id, raw_task)
        existing.add(task_name)
        inserted.append(task_name)
    if inserted:
        conn.commit()
    return inserted
