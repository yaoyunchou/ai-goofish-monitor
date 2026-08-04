"""
运行时可公开的配置摘要（不含密钥明文）。
"""
from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import urlparse

from src.infrastructure.config.env_manager import env_manager
from src.infrastructure.config.settings import AISettings, scraper_settings
from src.infrastructure.persistence.database_config import DRIVER_POSTGRES


_RUNTIME_KEYS = (
    "AI_PROVIDER",
    "CURSOR_API_KEY",
    "CURSOR_MODEL_NAME",
    "CURSOR_RUNTIME",
    "OPENAI_API_KEY",
    "DATABASE_URL",
    "SERVER_PORT",
)


def _config_source(key: str) -> str:
    """env_file | process_env | unset"""
    return env_manager.config_source(key)


def _resolved_value(key: str, default: str | None = None) -> str | None:
    value = env_manager.get_value(key, default)
    if value is None or str(value).strip() == "":
        return default
    return str(value).strip()


def _mask_database_url(url: str | None) -> dict[str, Any]:
    if not url:
        return {"set": False, "host": None, "database": None}
    normalized = re.sub(r"^postgresql\+asyncpg://", "postgresql://", url.strip(), count=1)
    normalized = re.sub(r"^postgresql\+psycopg://", "postgresql://", normalized, count=1)
    try:
        parsed = urlparse(normalized)
        host = parsed.hostname or None
        database = (parsed.path or "").lstrip("/") or None
        return {"set": True, "host": host, "database": database}
    except Exception:  # noqa: BLE001
        return {"set": True, "host": None, "database": None}


def build_runtime_config_summary() -> dict[str, Any]:
    ai = AISettings()
    database_url = _resolved_value("DATABASE_URL")
    variables: dict[str, dict[str, Any]] = {}
    for key in _RUNTIME_KEYS:
        secret = key.endswith("_KEY") or key.endswith("_TOKEN") or key == "DATABASE_URL"
        source = _config_source(key)
        entry: dict[str, Any] = {"source": source, "set": source != "unset"}
        if not secret and source != "unset":
            entry["value"] = _resolved_value(key)
        variables[key] = entry

    return {
        "env_file_path": str(env_manager.env_file.resolve()),
        "env_file_exists": env_manager.env_file.exists(),
        "cursor_agent": os.getenv("CURSOR_AGENT") == "1",
        "server_port": _resolved_value("SERVER_PORT", "8000"),
        "database_driver": DRIVER_POSTGRES,
        "database_url": _mask_database_url(database_url),
        "ai_provider": ai.normalized_provider(),
        "cursor_runtime_effective": ai.effective_cursor_runtime(),
        "ai_configured": ai.is_configured(),
        "headless_mode": scraper_settings.run_headless,
        "running_in_docker": scraper_settings.running_in_docker,
        "variables": variables,
    }
