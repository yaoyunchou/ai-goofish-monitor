"""列出当前进程可见的环境变量键（不打印值）。"""
from __future__ import annotations

import os

# 与项目相关的键
KEYS = [
    "AI_PROVIDER",
    "CURSOR_API_KEY",
    "CURSOR_MODEL_NAME",
    "CURSOR_RUNTIME",
    "CURSOR_AGENT",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "OPENAI_MODEL_NAME",
    "DATABASE_URL",
    "SERVER_PORT",
    "WEB_USERNAME",
    "WEB_PASSWORD",
    "RUN_HEADLESS",
]


def main() -> None:
    print("=== 环境变量键是否已设置（仅 true/false，不显示值）===\n")
    for key in KEYS:
        val = os.environ.get(key)
        if val is None or str(val).strip() == "":
            print(f"  {key}: 未设置")
        else:
            print(f"  {key}: 已设置 (长度 {len(str(val))})")

    print("\n提示: Cursor Secrets 注入后键名应与上表一致；部分环境不在 shell 中回显 Secrets。")


if __name__ == "__main__":
    main()
