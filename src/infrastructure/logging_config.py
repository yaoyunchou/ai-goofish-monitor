"""Uvicorn 日志配置：debugpy 会 detach stdout，统一写到 stderr 避免日志崩溃掩盖真实异常。"""
import logging
import sys

from pathlib import Path

# 供 uvicorn.run(log_config=...) 与 --log-config 共用
UVICORN_LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "()": "uvicorn.logging.DefaultFormatter",
            "fmt": "%(levelprefix)s %(message)s",
            "use_colors": None,
        },
        "access": {
            "()": "uvicorn.logging.AccessFormatter",
            "fmt": '%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s',
        },
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
        "access": {
            "formatter": "access",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
    },
    "loggers": {
        "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": False},
        "uvicorn.error": {"level": "INFO"},
        "uvicorn.access": {"handlers": ["access"], "level": "INFO", "propagate": False},
    },
}


def configure_app_logging() -> None:
    """应用内业务日志也走 stderr，与 uvicorn 一致。"""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    app_logger = logging.getLogger("app")
    if not app_logger.handlers:
        app_logger.addHandler(handler)
        app_logger.setLevel(logging.INFO)
        app_logger.propagate = False


def configure_scheduler_file_logging(log_dir: str = "logs") -> Path:
    """把 APScheduler 触发/错过写到 logs/scheduler.log，避免只打在 cmd 窗口里无处可查。"""
    directory = Path(log_dir)
    directory.mkdir(parents=True, exist_ok=True)
    log_path = directory / "scheduler.log"
    logger = logging.getLogger("apscheduler")
    logger.setLevel(logging.INFO)
    abs_path = str(log_path.resolve())
    for existing in logger.handlers:
        if isinstance(existing, logging.FileHandler) and getattr(existing, "baseFilename", None) == abs_path:
            return log_path
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    return log_path
