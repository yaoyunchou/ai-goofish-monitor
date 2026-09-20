#!/usr/bin/env python3
"""从 Supabase MCP 导出构建 data/db_sync_snapshot/*.json（无需 DB 密码）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts.mcp_extract_rows import extract_rows  # noqa: E402
from scripts.sync_postgres_remote_to_local import TABLE_ORDER  # noqa: E402

OUT = _REPO / "data" / "db_sync_snapshot"
MCP_RESULT_ITEMS = Path(
    r"C:\Users\yao\.cursor\projects\c-Users-yao-Desktop-work-2026-ai-goofish-monitor"
    r"\agent-tools\0fa77dd3-6e07-4cb5-88bc-d43bc079f7b5.txt"
)
MCP_PRICE_PARTS = (
    _REPO / "data" / "mcp_exports" / "price_part1.txt",
    _REPO / "data" / "mcp_exports" / "price_part2.txt",
)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    app_metadata = [
        {"key": "bootstrap:legacy_price_snapshots", "value": "done"},
        {"key": "bootstrap:legacy_results", "value": "done"},
        {"key": "bootstrap:legacy_tasks", "value": "done"},
        {"key": "migration:result_items_status", "value": "done"},
    ]
    tasks = [
        {
            "id": 0,
            "task_name": "机乐堂30w多口充电头",
            "enabled": True,
            "keyword": "机乐堂 30w 充电头",
            "description": "监控闲鱼机乐堂品牌30W充电头，排除纯数据线与非机乐堂品牌。",
            "analyze_images": True,
            "max_pages": 3,
            "personal_only": True,
            "min_price": "30",
            "max_price": "150",
            "cron": "0 */2 * * *",
            "ai_prompt_base_file": "prompts/base_prompt.txt",
            "ai_prompt_criteria_file": "prompts/机乐堂_30w_充电头_多口_criteria.txt",
            "account_state_file": None,
            "account_strategy": "auto",
            "free_shipping": True,
            "new_publish_option": "",
            "region": "",
            "decision_mode": "ai",
            "keyword_rules_json": [],
            "is_running": False,
        },
        {
            "id": 1,
            "task_name": "天才知音故事机",
            "enabled": True,
            "keyword": "天才知音全新儿童故事机早教机智能学习机随身听",
            "description": "关键词模式：匹配标题含天才知音等关键词的闲置故事机/早教机。",
            "analyze_images": False,
            "max_pages": 3,
            "personal_only": False,
            "min_price": None,
            "max_price": None,
            "cron": "0 */2 * * *",
            "ai_prompt_base_file": "prompts/base_prompt.txt",
            "ai_prompt_criteria_file": "",
            "account_state_file": None,
            "account_strategy": "auto",
            "free_shipping": False,
            "new_publish_option": "",
            "region": "",
            "decision_mode": "keyword",
            "keyword_rules_json": ["天才知音", "故事机"],
            "is_running": False,
        },
    ]
    result_blacklist_rules = [
        {
            "result_filename": "macbook_air_m1_full_data.jsonl",
            "blacklist_keywords_json": ["intel"],
            "updated_at": "2026-08-04T01:44:44.493955",
        }
    ]
    result_items = extract_rows(MCP_RESULT_ITEMS.read_text(encoding="utf-8"))
    if not all(p.is_file() for p in MCP_PRICE_PARTS):
        print("未找到 price MCP 分片，price_snapshots 将为空（可配置 REMOTE_DATABASE_URL 后重跑 pull）")
        price_snapshots = []
    else:
        price_snapshots = []
        for p in MCP_PRICE_PARTS:
            price_snapshots.extend(extract_rows(p.read_text(encoding="utf-8")))
    snapshots = {
        "app_metadata": app_metadata,
        "tasks": tasks,
        "result_items": result_items,
        "price_snapshots": price_snapshots,
        "result_blacklist_rules": result_blacklist_rules,
        "collected_items": [],
    }
    for table in TABLE_ORDER:
        (OUT / f"{table}.json").write_text(
            json.dumps(snapshots[table], ensure_ascii=False), encoding="utf-8"
        )
        print(f"{table}: {len(snapshots[table])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
