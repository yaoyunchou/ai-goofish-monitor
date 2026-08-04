"""Postgres 方言相关 SQL 片段与类型辅助。"""
from __future__ import annotations

import json
from typing import Any


def sql_true_condition(column: str) -> str:
    return f"{column} IS TRUE"


def insert_result_item_ignore_sql() -> str:
    columns = """
        result_filename, keyword, task_name, crawl_time, publish_time, price,
        price_display, item_id, title, link, link_unique_key, seller_nickname,
        is_recommended, analysis_source, keyword_hit_count, raw_json
    """
    placeholders = ", ".join(["%s"] * 16)
    return f"""
        INSERT INTO result_items ({columns})
        VALUES ({placeholders})
        ON CONFLICT (result_filename, link_unique_key) DO NOTHING
    """


def insert_price_snapshot_ignore_sql() -> str:
    columns = """
        keyword_slug, keyword, task_name, snapshot_time, snapshot_day,
        run_id, item_id, title, price, price_display, tags_json, region,
        seller, publish_time, link
    """
    placeholders = ", ".join(["%s"] * 15)
    return f"""
        INSERT INTO price_snapshots ({columns})
        VALUES ({placeholders})
        ON CONFLICT (keyword_slug, run_id, item_id) DO NOTHING
    """


def upsert_app_metadata_sql() -> str:
    return """
        INSERT INTO app_metadata(key, value) VALUES (%s, %s)
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
    """


def upsert_task_sql() -> str:
    columns = """
        id, task_name, enabled, keyword, description, analyze_images,
        max_pages, personal_only, min_price, max_price, cron,
        ai_prompt_base_file, ai_prompt_criteria_file, account_state_file,
        account_strategy, free_shipping, new_publish_option, region,
        decision_mode, keyword_rules_json, is_running
    """
    return f"""
        INSERT INTO tasks ({columns}) VALUES (
            :id, :task_name, :enabled, :keyword, :description, :analyze_images,
            :max_pages, :personal_only, :min_price, :max_price, :cron,
            :ai_prompt_base_file, :ai_prompt_criteria_file, :account_state_file,
            :account_strategy, :free_shipping, :new_publish_option, :region,
            :decision_mode, :keyword_rules_json, :is_running
        )
        ON CONFLICT (id) DO UPDATE SET
            task_name = EXCLUDED.task_name,
            enabled = EXCLUDED.enabled,
            keyword = EXCLUDED.keyword,
            description = EXCLUDED.description,
            analyze_images = EXCLUDED.analyze_images,
            max_pages = EXCLUDED.max_pages,
            personal_only = EXCLUDED.personal_only,
            min_price = EXCLUDED.min_price,
            max_price = EXCLUDED.max_price,
            cron = EXCLUDED.cron,
            ai_prompt_base_file = EXCLUDED.ai_prompt_base_file,
            ai_prompt_criteria_file = EXCLUDED.ai_prompt_criteria_file,
            account_state_file = EXCLUDED.account_state_file,
            account_strategy = EXCLUDED.account_strategy,
            free_shipping = EXCLUDED.free_shipping,
            new_publish_option = EXCLUDED.new_publish_option,
            region = EXCLUDED.region,
            decision_mode = EXCLUDED.decision_mode,
            keyword_rules_json = EXCLUDED.keyword_rules_json,
            is_running = EXCLUDED.is_running
    """


def as_sql_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return value is not None and str(value).strip().lower() in {"1", "true", "yes", "on"}


def parse_json_field(value: Any, *, default: Any):
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def insert_collected_item_sql() -> str:
    return """
        INSERT INTO collected_items (
            result_item_id, collected_at, sku_fetch_status
        ) VALUES (%s, %s, 'pending')
        RETURNING id
    """


def json_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)
