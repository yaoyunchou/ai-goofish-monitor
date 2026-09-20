#!/bin/bash

# 本地开发：后端 uvicorn --reload + 前端 Vite HMR（不构建 dist）
# 数据库请自行先起：docker compose -f docker-compose.dev.yml up -d

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

read_server_port() {
  if [ -f .env ]; then
    local val
    val="$(grep -E '^SERVER_PORT=' .env | tail -1 | cut -d= -f2- | tr -d '\r' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    if [ -n "$val" ]; then
      echo "$val"
      return
    fi
  fi
  echo "8000"
}

OS_FAMILY="unknown"
PYTHON_BOOT="python3"
case "$(uname -s 2>/dev/null || echo unknown)" in
  MINGW*|MSYS*|CYGWIN*)
    OS_FAMILY="windows"
    if command -v python >/dev/null 2>&1; then
      PYTHON_BOOT="python"
    elif command -v py >/dev/null 2>&1; then
      PYTHON_BOOT="py"
    fi
    ;;
esac

VENV_DIR="$SCRIPT_DIR/.venv"
if [ "$OS_FAMILY" = "windows" ]; then
  VENV_PYTHON="$VENV_DIR/Scripts/python.exe"
else
  VENV_PYTHON="$VENV_DIR/bin/python"
fi

if [ ! -f "$VENV_PYTHON" ]; then
  echo -e "${YELLOW}创建 .venv...${NC}"
  "$PYTHON_BOOT" -m venv "$VENV_DIR"
fi

PIP_CMD=("$VENV_PYTHON" -m pip)

if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  echo -e "${RED}✗ 需要 Node.js 与 npm${NC}"
  exit 1
fi

SERVER_PORT="$(read_server_port)"
export SERVER_PORT

UVICORN_PID=""
VITE_PID=""

cleanup() {
  echo -e "\n${YELLOW}正在停止开发服务...${NC}"
  if [ -n "$VITE_PID" ]; then
    kill "$VITE_PID" 2>/dev/null || true
  fi
  if [ -n "$UVICORN_PID" ]; then
    kill "$UVICORN_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}闲鱼监控系统 - 开发模式 (reload)${NC}"
echo -e "${GREEN}========================================${NC}"

echo -e "\n${YELLOW}[1/3] Python 依赖...${NC}"
"${PIP_CMD[@]}" install -r requirements.txt -q
echo -e "${GREEN}✓ Python 依赖就绪${NC}"

echo -e "\n${YELLOW}[2/3] 前端依赖...${NC}"
if [ ! -d "web-ui/node_modules" ]; then
  (cd web-ui && npm install)
else
  echo -e "${GREEN}✓ web-ui/node_modules 已存在${NC}"
fi

echo -e "\n${YELLOW}[3/3] 启动服务...${NC}"
echo -e "  后端 API:  http://127.0.0.1:${SERVER_PORT}  (uvicorn --reload)"
echo -e "  前端 UI:   见下方 Vite 输出的 Local 地址 (通常 http://127.0.0.1:5173)"
echo -e "  数据库:    请确保 Postgres 已运行 (docker compose -f docker-compose.dev.yml up -d)"
echo ""

"$VENV_PYTHON" -m uvicorn src.app:app --host 0.0.0.0 --port "$SERVER_PORT" --reload &
UVICORN_PID=$!

(cd web-ui && npm run dev) &
VITE_PID=$!

wait $UVICORN_PID $VITE_PID
