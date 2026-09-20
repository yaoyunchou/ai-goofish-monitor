# Repository Guidelines

## ⚠️ 首要规则：只改代码，不要运行服务（必读）

**智能体只负责修改代码，不得启动或运行任何服务。所有运行一律由用户手动执行。**

- **禁止**代跑 `start.sh` / `start.bat` / `dev_start.bat` / `python -m src.app` /
  `npm run dev` / `uvicorn ...` / `docker compose up` / `spider_v2.py` 等
  任何会占用端口或产生常驻进程的命令。
- 验证改动请使用**静态手段**：`pytest`、`npx vue-tsc -b --noEmit`、`npx vitest run`、
  代码阅读与类型检查。**不要**用「先起服务再 curl」的方式验证。
- 如因特殊原因确实启动了进程，**必须在同一次任务内关闭**，并确认端口已释放
  （`netstat -ano | findstr ":<port> "`）。
- 开发完成后**不要**主动把服务跑起来，也不要把「起服务给用户测试」当作收尾步骤。

> 原因：历史上多次出现智能体启动的服务未关闭，遗留进程占用端口，
> 导致用户下次手动启动时遭遇「端口被占用」，排查成本很高。

## 本地端口约定

- 本项目本地开发端口为 **8010**（读 `.env` 的 `SERVER_PORT`）。
- 本机 **`8000` 被用户的另一个项目（「物流爬虫控制台」，`uvicorn server:app`）长期占用**，
  不要占用它，也不要结束它的进程。
- 前端 dev server 使用 **5173**。

## 项目结构与模块组织
- 后端位于 `src/`，入口 `src/app.py`，API 路由在 `src/api/routes/`，服务层在 `src/services/`，领域模型在 `src/domain/`，基础设施在 `src/infrastructure/`。
- 前端在 `web-ui/`（Vue 3 + Vite），视图放于 `web-ui/src/views/`，组件在 `web-ui/src/components/`，构建产物会复制到根目录 `dist/`。
- 测试位于 `tests/`，命名遵循 `test_*.py` 或 `tests/*/test_*.py`。
- 运行数据与资源：`prompts/`、`jsonl/`、`logs/`、`images/`、`static/`、`state/`，配置文件 `config.json` 与 `.env`（含 `DATABASE_URL`）位于仓库根目录。

## 构建、测试与本地开发
- **虚拟环境**：项目使用 `.venv`（Python 3.11+）。首次：`python -m venv .venv && source .venv/Scripts/activate && python -m pip install -r requirements.txt`（Linux/macOS 用 `.venv/bin/activate`）。`.venv/` 已在 `.gitignore` 中，勿提交。`start.sh` 会自动优先使用 `.venv`。
  - 注意：本机当前**并未创建 `.venv`**，实际运行用的是系统 Python（`C:\python\python.exe`，3.12）。`start.bat` / `dev_start.bat` 会自动回退到系统解释器，不要因为找不到 `.venv` 就报错或去创建它。
- 后端开发：`python -m src.app` 或 `uvicorn src.app:app --host 0.0.0.0 --port 8010 --reload`（须在 `.venv` 激活状态下执行）。
- 爬虫任务：`python spider_v2.py --task-name "MacBook Air M1" --debug-limit 3`（可用 `--config` 指定自定义配置）。
- 前端开发：`cd web-ui && npm install && npm run dev`；构建：`cd web-ui && npm run build`（产物复制到根目录 `dist/`）；单测：`cd web-ui && npm test`（Vitest smoke）。
- 一键本地启动：`bash start.sh`（自动安装依赖、前端构建并启动后端）。
- Docker：`docker compose up --build -d`，查看日志 `docker compose logs -f app`，停止 `docker compose down`。

## 编码风格与命名约定
- 保持分层：API → services → domain → infrastructure，避免跨层耦合，模块保持精简。
- Python 测试函数命名为 `test_*`，文件与路径遵循上述测试目录规范。
- 使用描述性、任务导向的命名（如爬虫任务名、配置键），与业务含义对应。

## 架构与运行时
- 后端使用 FastAPI 提供 API 与静态资源，爬虫与 AI 推理在独立任务进程中协作，前后端通过 HTTP/Web UI 交互。
- 主数据在 **PostgreSQL**（`.env` 的 `DATABASE_URL`）；任务结果等写入数据库，`jsonl/` 仍可作为爬虫输出与 bootstrap 来源。
- 默认监听 8010 端口（读 `.env` 的 `SERVER_PORT`），前端构建后静态文件可由后端或 Docker 镜像直接提供。

## 测试指南
- 测试框架：`pytest`（默认同步测试，无需 `pytest-asyncio`）。
- 运行全部测试：`python -m pytest -q`；覆盖率：`pytest --cov=src`；详见 `tests/README.md`。
- CI：`.github/workflows/pytest.yml` 在 push/PR 时自动运行。
- 优先覆盖核心服务、爬虫管道的异常分支与重试逻辑，避免回归。
- **PR 必须**：`pytest` 全绿；新功能同步更新 `docs/features.md` / `user-guide.md` 与对应测试。

## 提交与 PR 规范
- Commit 采用类 Conventional Commits：`feat(...)`、`fix(...)`、`refactor(...)`、`chore(...)`、`docs(...)` 等。
- PR 需说明变更范围与影响模块；UI 变更在 `web-ui/` 提供截图；关联相关 Issue；提及配置或迁移步骤。

## 安全与配置提示
- 复制 `.env.example` 为 `.env`，配置 **`DATABASE_URL`**（PostgreSQL）及 `AI_PROVIDER`（`openai` 或 `cursor`）与对应 API Key（见 `docs/ai-provider.md`、`docs/design/database-supabase-integration.md`）。
- 不要提交真实凭据或 cookies（如 `state.json`）；Playwright 需本地浏览器，Docker 镜像已预装 Chromium。
- Web 认证默认 `admin/admin123`，生产环境务必修改，推荐启用 HTTPS 并限制访问来源。
