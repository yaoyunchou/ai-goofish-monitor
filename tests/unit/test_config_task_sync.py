import json

from src.infrastructure.persistence.config_task_sync import sync_missing_tasks_from_config
from src.infrastructure.persistence.db_connection import db_connection
from src.infrastructure.persistence.sqlite_connection import init_schema


def test_sync_missing_tasks_from_config_inserts_only_new_names(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            [
                {
                    "task_name": "任务A",
                    "enabled": True,
                    "keyword": "kw-a",
                    "description": "需求A",
                    "max_pages": 2,
                    "personal_only": True,
                    "ai_prompt_base_file": "prompts/base_prompt.txt",
                    "ai_prompt_criteria_file": "prompts/a_criteria.txt",
                    "decision_mode": "ai",
                },
                {
                    "task_name": "任务B",
                    "enabled": True,
                    "keyword": "kw-b",
                    "description": "需求B",
                    "max_pages": 1,
                    "personal_only": True,
                    "ai_prompt_base_file": "prompts/base_prompt.txt",
                    "ai_prompt_criteria_file": "prompts/b_criteria.txt",
                    "decision_mode": "ai",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    db_path = tmp_path / "test.sqlite3"
    with db_connection(str(db_path)) as conn:
        init_schema(conn.raw)
        conn.execute(
            """
            INSERT INTO tasks (
                id, task_name, enabled, keyword, description, analyze_images,
                max_pages, personal_only, min_price, max_price, cron,
                ai_prompt_base_file, ai_prompt_criteria_file, account_state_file,
                account_strategy, free_shipping, new_publish_option, region,
                decision_mode, keyword_rules_json, is_running
            ) VALUES (0, '任务A', 1, 'kw-a', '需求A', 1, 2, 1, NULL, NULL, NULL,
                'prompts/base_prompt.txt', 'prompts/a_criteria.txt', NULL, 'auto', 1,
                NULL, NULL, 'ai', '[]', 0)
            """
        )
        conn.commit()
        inserted = sync_missing_tasks_from_config(conn, str(config_path))
    assert inserted == ["任务B"]
    with db_connection(str(db_path)) as conn:
        rows = conn.execute("SELECT task_name FROM tasks ORDER BY id ASC").fetchall()
    names = [row["task_name"] for row in rows]
    assert names == ["任务A", "任务B"]
