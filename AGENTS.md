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
- 复制 `.env.example` 为 `.env`，设置必填项 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL_NAME` 等。
- 不要提交真实凭据或 cookies（如 `state.json`）；Playwright 需本地浏览器，Docker 镜像已预装 Chromium。
- Web 认证默认 `admin/admin123`，生产环境务必修改，推荐启用 HTTPS 并限制访问来源。

## Cursor Cloud specific instructions
- 依赖（Python 包、Playwright Chromium、`web-ui` 前端包）已由启动更新脚本安装，无需再手动安装。
- 后端只托管仓库根目录的 `dist/`，而 `dist/` 不在 git 中且**不由更新脚本构建**。首次启动前必须先构建前端，否则页面会提示前端构建产物不存在：`cd web-ui && npm run build`（产物会复制到根目录 `dist/`），或直接运行 `bash start.sh`（它会先构建再启动后端）。仅改动后端代码时无需重建。
- 启动后端：`python3 -m src.app`（监听 `:8000`）。若需前端热更新，另开 `cd web-ui && npm run dev`（`:5173`，代理 `/api`、`/auth`、`/ws` 到 `:8000`，需后端同时运行）。
- 无需真实 AI Key 也能启动并使用 Web UI；SQLite（`data/app.sqlite3`）在启动时自动建库。要不依赖外部 AI 地验证核心功能，创建任务时选择 `decision_mode=keyword`（关键词判断），跳过 AI 生成流程。真正抓取闲鱼还需在 `state/` 放置有效登录态，并配置 `OPENAI_*`。
- 运行测试：`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest`。当前 master 上有 2 个与环境无关的既有失败：`tests/test_frontend_build_paths.py::test_frontend_build_output_path_is_consistent_across_configs` 和 `tests/unit/test_utils.py::test_save_to_jsonl`。标记为 `live` 的测试默认跳过（需真实凭据，见 `run_live_smoke.sh`）。
- `pip` 需加 `--break-system-packages`（PEP 668），包会装到用户目录 `~/.local`；用 `python3 -m <tool>`（如 `python3 -m pytest`）调用即可，无需把 `~/.local/bin` 加入 PATH。
