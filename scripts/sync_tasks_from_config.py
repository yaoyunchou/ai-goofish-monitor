#!/usr/bin/env python3
"""
将 config.json 中尚未入库的任务同步到当前配置的数据库。

用法（在项目根目录）:
  python -m scripts.sync_tasks_from_config
  python -m scripts.sync_tasks_from_config --config /path/to/config.json
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

load_dotenv(_REPO_ROOT / ".env", override=False)

from src.infrastructure.persistence.config_task_sync import (
    _load_config_tasks,
    sync_missing_tasks_from_config,
)
from src.infrastructure.persistence.db_connection import db_connection  # noqa: E402
from src.infrastructure.persistence.storage_bootstrap import LEGACY_CONFIG_FILE, bootstrap_storage  # noqa: E402
from src.infrastructure.persistence.storage_names import build_result_filename  # noqa: E402
from src.services.result_storage_service import save_result_blacklist_keywords  # noqa: E402

DEFAULT_BLACKLIST = ["卡斐乐", "数据线", "快充线", "充电线", "仅线", "转接头"]


async def _seed_blacklist_for_keyword(keyword: str) -> None:
    filename = build_result_filename(keyword)
    await save_result_blacklist_keywords(filename, DEFAULT_BLACKLIST)


async def main(config_file: str) -> int:
    from src.infrastructure.persistence.database_config import get_database_driver

    driver = get_database_driver()
    print(f"当前数据库驱动: {driver}")
    bootstrap_storage(legacy_config_file=config_file)
    with db_connection() as conn:
        inserted = sync_missing_tasks_from_config(conn, config_file)
    if not inserted:
        print("没有需要同步的新任务（config 中的 task_name 均已存在）。")
        return 0
    print(f"已同步 {len(inserted)} 个任务: {', '.join(inserted)}")
    config_tasks = {str(t.get("task_name")): t for t in _load_config_tasks(Path(config_file))}
    for name in inserted:
        raw = config_tasks.get(name) or {}
        keyword = str(raw.get("keyword") or name)
        await _seed_blacklist_for_keyword(keyword)
    print("已为上述任务写入默认结果黑名单规则。")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="从 config.json 同步缺失监控任务到数据库")
    parser.add_argument(
        "--config",
        default=LEGACY_CONFIG_FILE,
        help=f"任务配置文件路径（默认 {LEGACY_CONFIG_FILE}）",
    )
    args = parser.parse_args()
    try:
        raise SystemExit(asyncio.run(main(args.config)))
    except Exception as exc:
        print(f"同步失败: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
