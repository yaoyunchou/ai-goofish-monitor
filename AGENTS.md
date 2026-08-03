# Repository Guidelines

## 项目结构与模块组织
- 后端位于 `src/`，入口 `src/app.py`，API 路由在 `src/api/routes/`，服务层在 `src/services/`，领域模型在 `src/domain/`，基础设施在 `src/infrastructure/`。
- 前端在 `web-ui/`（Vue 3 + Vite），视图放于 `web-ui/src/views/`，组件在 `web-ui/src/components/`，构建产物会复制到根目录 `dist/`。
- 测试位于 `tests/`，命名遵循 `test_*.py` 或 `tests/*/test_*.py`。
- 运行数据与资源：`prompts/`、`jsonl/`、`logs/`、`images/`、`static/`、`state/`，配置文件 `config.json` 与 `.env` 位于仓库根目录。

## 构建、测试与本地开发
- 后端开发：`python -m src.app` 或 `uvicorn src.app:app --host 0.0.0.0 --port 8000 --reload`。
- 爬虫任务：`python spider_v2.py --task-name "MacBook Air M1" --debug-limit 3`（可用 `--config` 指定自定义配置）。
- 前端开发：`cd web-ui && npm install && npm run dev`；构建：`cd web-ui && npm run build`（产物复制到根目录 `dist/`）。
- 一键本地启动：`bash start.sh`（自动安装依赖、前端构建并启动后端）。
- Docker：`docker compose up --build -d`，查看日志 `docker compose logs -f app`，停止 `docker compose down`。

## 编码风格与命名约定
- 保持分层：API → services → domain → infrastructure，避免跨层耦合，模块保持精简。
- Python 测试函数命名为 `test_*`，文件与路径遵循上述测试目录规范。
- 使用描述性、任务导向的命名（如爬虫任务名、配置键），与业务含义对应。

## 架构与运行时
- 后端使用 FastAPI 提供 API 与静态资源，爬虫与 AI 推理在独立任务进程中协作，前后端通过 HTTP/Web UI 交互。
- 任务运行会在 `jsonl/` 写入结果、在 `logs/` 留存运行日志、在 `images/` 下载图片，前端监控页面依赖这些数据。
- 默认监听 8000 端口，前端构建后静态文件可由后端或 Docker 镜像直接提供。

## 测试指南
- 测试框架：`pytest`（默认同步测试，无需 `pytest-asyncio`）。
- 运行全部测试：`pytest`；覆盖率：`pytest --cov=src` 或 `coverage run -m pytest`；定向测试：`pytest tests/test_utils.py::test_safe_get`。
- 优先覆盖核心服务、爬虫管道的异常分支与重试逻辑，避免回归。
- PR 前请运行相关测试，新增逻辑补充针对性用例。

## 提交与 PR 规范
- Commit 采用类 Conventional Commits：`feat(...)`、`fix(...)`、`refactor(...)`、`chore(...)`、`docs(...)` 等。
- PR 需说明变更范围与影响模块；UI 变更在 `web-ui/` 提供截图；关联相关 Issue；提及配置或迁移步骤。

## 安全与配置提示
- 复制 `.env.example` 为 `.env`，设置 `AI_PROVIDER`（`openai` 或 `cursor`）及对应 API Key；OpenAI 兼容模式需 `OPENAI_*`，Cursor 模式需 `CURSOR_API_KEY` 等（见 `docs/ai-provider.md`）。
- 不要提交真实凭据或 cookies（如 `state.json`）；Playwright 需本地浏览器，Docker 镜像已预装 Chromium。
- Web 认证默认 `admin/admin123`，生产环境务必修改，推荐启用 HTTPS 并限制访问来源。

## Cursor Cloud specific instructions
本节面向在已执行 update 脚本（`pip install -r requirements.txt`、`web-ui` 的 `npm install`、`playwright install chromium`）后的 Cloud Agent，只记录非显而易见的启动/运行注意点，常规命令见 `AGENTS.md`/`CLAUDE.md`/`README.md`。

- 解释器只有 `python3`，没有 `python`；`start.sh`、README 里的 `python -m ...` 需改用 `python3 -m ...`（如 `python3 -m src.app`）。
- 依赖装在用户目录（`~/.local`），Playwright Chromium 与系统库 `libzbar0` 已随环境就绪，无需额外安装系统包。
- 前端 dev server（`cd web-ui && npm run dev`）绑定的是 IPv6 loopback，请用 `http://localhost:5173` 访问，`http://127.0.0.1:5173` 会连不上；它把 `/api`、`/auth`、`/ws` 代理到后端 8000 端口。
- 数据库坑（重要）：本环境把 `DATABASE_DRIVER` 设为非 sqlite 的 PG 驱动值，并注入了一个指向 `db.wkhatdhgohkpsqkytotz.supabase.co`（Supabase 直连）的 `DATABASE_URL` secret。该直连主机仅有 IPv6 记录，而 Cloud VM 只有 IPv4 出口，因此 `python3 -m src.app` 启动时会以 `Network is unreachable` 崩溃。经实测该项目位于 `ap-northeast-1`，但即便改用 IPv4 Session pooler（`aws-0-ap-northeast-1.pooler.supabase.com:5432`，用户名为「项目 ref 前缀」的 pooler 账号），注入的密码也会 `password authentication failed`。因此如需本地起服务，请在启动会话内把驱动覆盖为 sqlite（零配置默认路径，数据落到 `data/app.sqlite3`）：`DATABASE_DRIVER=sqlite python3 -m src.app`。若要让服务默认连 Supabase，需要项目所有者把 `DATABASE_URL` secret 更新为「IPv4 Session pooler 主机 + 正确 DB 密码」。
- `pytest` 已在 `tests/conftest.py` 强制使用 sqlite 驱动，与上面的 secret 无关，可直接 `python3 -m pytest`。当前 `master` 上有 10 个预存在的失败用例（`test_ai_handler_analysis.py` 仍引用已重构掉的 `ai_handler.client`、`test_save_to_jsonl`/`test_item_detail_parser` 等期望旧数据结构），属历史用例未同步，并非环境问题。
- 无 lint 工具（无 ruff/black/flake8/eslint）；唯一静态检查是前端 `npm run build` 内置的 `vue-tsc` 类型检查（产物输出到根目录 `dist/`）。
