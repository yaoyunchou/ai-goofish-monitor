# 闲鱼智能监控系统

[中文] ｜ [English](README_EN.md)

基于 Playwright 和 AI 的闲鱼多任务实时监控，提供完整的 Web 管理界面。

## 📚 详细文档

完整使用说明见 [`docs/`](./docs/README.md) 目录：

- [用户使用指南](./docs/user-guide.md) — 安装、配置、日常使用
- [闲鱼 Cookie 获取指南](./docs/getting-xianyu-cookies.md) — 开发者工具手动抓 Cookie / Chrome 扩展导入
- [AI 提供方配置：OpenAI 与 Cursor SDK](./docs/ai-provider.md) — OpenAI 兼容接口与 Cursor SDK 切换说明


## 核心特性

- **Web 可视化管理**: 任务管理、账号管理、AI 标准编辑、运行日志、结果浏览
- **AI 驱动**: 自然语言创建任务，多模态模型深度分析商品
- **多任务并发**: 独立配置关键词、价格、筛选条件和 AI Prompt
- **高级筛选**: 包邮、新发布时间范围、省/市/区三级区域筛选
- **即时通知**: 支持 ntfy.sh、企业微信、Bark、Telegram、Webhook等多渠道
- **定时调度**: 支持 Cron 配置周期性任务
- **账号与代理轮换**: 多账号管理、任务绑定账号、代理池轮换与失败重试
- **Docker 部署**: 一键容器化部署

## 截图

![监控概览](static/img.png)
![任务管理](static/img_1.png)
![结果查看](static/img_2.png)
![通知推送](static/img_3.png)

## 🐳 Docker 部署（推荐）

```bash
git clone https://github.com/Usagi-org/ai-goofish-monitor && cd ai-goofish-monitor
cp .env.example .env
vim .env # 填写相关配置项
docker compose up -d
docker compose logs -f app
docker compose down
```

如果镜像无法访问或下载速度慢，可尝试使用加速：
```bash

docker pull ghcr.nju.edu.cn/usagi-org/ai-goofish:latest
docker tag ghcr.nju.edu.cn/usagi-org/ai-goofish:latest ghcr.io/usagi-org/ai-goofish:latest
docker compose up -d

```

- 默认 Web UI 地址：`http://127.0.0.1:8000`
- Docker 镜像已内置 Chromium，无需宿主机额外安装浏览器。
- 官方镜像地址：`ghcr.io/usagi-org/ai-goofish:latest`
- 更新镜像：`docker compose pull && docker compose up -d`
- 如果你修改了 `.env` 中的 `SERVER_PORT`，请同步更新 `docker-compose.yaml` 里的端口映射。
- **数据库**：在 `.env` 配置 `DATABASE_URL`（PostgreSQL / Supabase）。**本地开发**可只起 `docker compose -f docker-compose.dev.yml` 提供 Postgres，应用仍在宿主机运行（见「开发者开发 → 日常本地调试」）。
- 默认持久化这些目录：
    - `state/`  登录状态 cookie 文件
    - `prompts/`  任务提示词
    - `logs/`  运行日志
    - `images/`  商品图片与任务临时图片目录
    - `config.json`、`jsonl/`、`price_history/`  首次启动时用于向 Postgres 导入历史数据（表为空时）

### 数据存储

- 主数据在 **PostgreSQL**（环境变量 `DATABASE_URL`）
- 启动时自动连接数据库；表为空时会尝试从 `config.json`、`jsonl/`、`price_history/` 导入一次
- `state/`、`prompts/`、`logs/`、`images/` 仍在文件系统
- 商品图片临时目录 `images/task_images_<task_name>/`，任务结束后默认清理

### 最少配置

| 变量 | 说明 | 必填 |
|------|------|------|
| `AI_PROVIDER` | AI 提供方：`openai`（默认）或 `cursor` | 否 |
| `OPENAI_API_KEY` | OpenAI 兼容 API Key（`AI_PROVIDER=openai` 时） | 是* |
| `OPENAI_BASE_URL` | OpenAI 兼容接口地址 | 是* |
| `OPENAI_MODEL_NAME` | 支持图片输入的模型名称 | 是* |
| `CURSOR_API_KEY` | Cursor API Key（`AI_PROVIDER=cursor` 时） | 是* |
| `CURSOR_MODEL_NAME` | Cursor 模型 ID，如 `composer-2.5` | 是* |
| `DATABASE_URL` | PostgreSQL 连接串（Supabase Session pooler 等） | 是 |
| `WEB_USERNAME` / `WEB_PASSWORD` | Web UI 登录账号密码，默认 `admin/admin123` | 否 |

\* 按所选 `AI_PROVIDER` 填写对应项，详见 [AI 提供方配置](./docs/ai-provider.md)。

其余配置见下方“配置说明”。


### 第一次使用

1. 打开默认 Web UI `http://127.0.0.1:8000` 并登录。
2. 按 [闲鱼 Cookie 获取指南](./docs/getting-xianyu-cookies.md) 导入登录态（推荐 Chrome 扩展，或开发者工具手动复制 Cookie）。
3. 登录态文件会保存到 `state/` 目录，例如 `state/acc_1.json`。
4. 按 [AI 提供方配置](./docs/ai-provider.md) 完成 AI 配置（OpenAI 兼容或 Cursor SDK）。
5. 回到「任务管理」，创建任务并绑定账号后即可运行。

### 创建第一个任务

- `AI判断`：填写“详细需求”，提交后会弹出独立进度弹窗，后台异步生成分析标准。
- `关键词判断`：填写关键词规则，任务会直接创建，不经过 AI 生成流程。
- `区域筛选`：已改为省 / 市 / 区三级选择器，数据基于闲鱼页面抓取快照内置。



## 用户使用说明

<details>
<summary>点击展开 Web UI 功能说明</summary>

### 任务管理

- 支持 AI 创建、关键词规则、价格范围、新发布范围、区域筛选、账号绑定、定时规则。
- AI 任务创建是后台 job 流程，提交后会打开单独的进度弹窗。
- 区域筛选会显著缩小结果集，默认留空。

### 账号管理

- 支持导入、更新、删除闲鱼账号登录态。
- 每个任务可指定账号，也可不绑定并交给系统自动选择。

### 结果查看与运行日志

- 结果页和导出从 **PostgreSQL** 查询，不再直接扫描 `jsonl` 文件。
- 日志页按任务展示运行过程，便于排查登录态失效、风控和 AI 调用问题。

### 系统设置

- 可查看系统状态、编辑 Prompt、调整代理与轮换相关配置。

</details>



## 开发者开发

### 日常本地调试（推荐）

**只有 PostgreSQL 用 Docker**，前后端都在本机跑，改代码立刻生效（后端 `--reload`、前端 Vite HMR）。  
**不要**为了改代码去跑 `docker compose up`（那是给服务器「整包部署」用的）。

```bash
# 1. 仅启动数据库（密码、库名见 docker-compose.dev.yml）
docker compose -f docker-compose.dev.yml up -d

# 2. .env 里数据库指向本机（与 dev 库一致）
# DATABASE_URL=postgresql+asyncpg://postgres:goofish@127.0.0.1:5432/goofish

# 3. 后端（热重载）— 或直接使用 ./start_dev.sh 同时起前后端
uvicorn src.app:app --host 0.0.0.0 --port 8000 --reload

# 4. 前端（另开终端）— start_dev.sh 会自动并行启动
cd web-ui && npm install && npm run dev
```

- 浏览器打开 Vite 提示的地址（一般是 `http://127.0.0.1:5173`），侧栏「收录商品」等**本地未发布功能**都在这里。
- `web-ui/vite.config.ts` 会从根目录 `.env` 读取 `SERVER_PORT` 作为 API 代理目标；与后端监听端口保持一致即可（可用 `./start_dev.sh` 一键对齐）。
- 停掉误起的**应用容器**（保留数据库）：`docker compose down`（不要对 `docker-compose.dev.yml` 执行 down，除非你要关库）。

| 场景 | 用什么 |
|------|--------|
| 本机写代码、调试 | 上表：dev Postgres + 本地 uvicorn + `npm run dev` |
| 服务器一键上线 | `docker compose up -d`（官方镜像） |
| 服务器要跑**你当前仓库**未发版功能 | `docker compose -f docker-compose.yaml -f docker-compose.local.yaml up -d --build` |

### 环境要求

- Python 3.10+
- Node.js + npm（本地验证 `Node v20.18.3` 可完成前端构建）
- Playwright CLI 与 Chromium，首次运行前建议执行 `python -m pip install playwright && python -m playwright install chromium`
- Chrome / Edge 浏览器（Linux 环境也可使用 Chromium；`start.sh` 会先检查浏览器是否存在）

```bash
git clone https://github.com/Usagi-org/ai-goofish-monitor
cd ai-goofish-monitor
cp .env.example .env
```

### 一键启动（推荐）

**生产式本地运行**（全量 build，无热更新）：

```bash
chmod +x start.sh
./start.sh
```

**开发模式**（后端 `--reload` + 前端 Vite HMR，推荐改代码时用）：

```bash
chmod +x start_dev.sh
./start_dev.sh
```

先确保数据库已启动：`docker compose -f docker-compose.dev.yml up -d`。  
开发时浏览器请打开 **Vite 地址**（一般为 `http://127.0.0.1:5173`），API 会按根目录 `.env` 的 `SERVER_PORT` 代理到本机后端。

`start.sh` 会自动完成以下步骤：

1. 检查环境与依赖（Python / Node / 浏览器）
2. **首次运行自动创建 `.venv` 虚拟环境**，后续所有 Python 操作均使用 `.venv`，不污染系统 Python
3. 安装 `requirements.txt` 到 `.venv`
4. 构建前端（`web-ui` → 根目录 `dist/`）
5. 启动后端服务

> Windows 用户在 Git Bash (MINGW64) 中运行即可；脚本会自动识别 `python` / `py` 命令。
> `.venv` 已加入 `.gitignore`，不会提交到仓库。

### 手动启动

#### 方式一：激活 .venv 后运行

```bash
# Git Bash / Linux / macOS
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1

# 激活后直接用 python
python -m src.app
# 或
uvicorn src.app:app --host 0.0.0.0 --port 8000 --reload
```

#### 方式二：不激活，直接用 .venv 的 python

```bash
# Git Bash / Linux / macOS
.venv/bin/python -m src.app

# Windows
.venv\Scripts\python.exe -m src.app
```

#### 前端开发

```bash
cd web-ui
npm install
npm run dev      # 开发模式，热更新，代理 /api 到后端
npm run build     # 生产构建，输出到根目录 dist/
```

- FastAPI 启动时连接 PostgreSQL；表为空时会尝试从 `config.json` / `jsonl/` / `price_history` 导入
- `spider_v2.py` 从数据库读取任务；仅 `--config <path>` 时使用 JSON 兼容模式
- Vite 开发服务器会将 `/api`、`/auth`、`/ws` 代理到 `http://127.0.0.1:8000`。
- `npm run build` 先生成 `web-ui/dist/`，`start.sh` 再复制到仓库根目录 `dist/`。
- FastAPI 负责提供根目录 `dist/index.html` 和 `dist/assets/`。
- `./start.sh` 默认输出访问地址 `http://localhost:8000` 和 API 文档 `http://localhost:8000/docs`。

### 测试与校验

```bash
# 使用 .venv 运行测试
.venv/bin/pytest
# 或 Windows
.venv\Scripts\python.exe -m pytest

cd web-ui && npm run build
```

### 任务创建 API

<details>
<summary>点击展开 API 行为说明</summary>

- `POST /api/tasks/generate`
  - `decision_mode=ai`：返回 `202` 和 `job`，需要继续轮询进度。
  - `decision_mode=keyword`：直接返回已创建任务。
- `GET /api/tasks/generate-jobs/{job_id}`：查询 AI 任务生成进度。
- `POST /auth/status`：校验 Web UI 登录凭据。

</details>

## 配置说明

<details>
<summary>点击展开常用配置项</summary>

### AI 与运行时

- `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL_NAME`：AI 模型接入必填项。
- `PROXY_URL`：为 AI 请求单独指定 HTTP/SOCKS5 代理。
- `RUN_HEADLESS`：是否以无头模式运行爬虫；Docker 中应保持 `true`。
- `SERVER_PORT`：后端监听端口，默认 `8000`。
- `LOGIN_IS_EDGE`：本地环境可切换为 Edge 内核；Docker 镜像未内置 Edge，容器内会固定使用 Chromium。
- `PCURL_TO_MOBILE`：是否将 PC 商品链接转换为移动端链接。

### 通知

- `NTFY_TOPIC_URL`
- `GOTIFY_URL` / `GOTIFY_TOKEN`
- `BARK_URL`
- `WX_BOT_URL`
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` / `TELEGRAM_API_BASE_URL`
- `WEBHOOK_*`

### 代理轮换与失败保护

- `PROXY_ROTATION_ENABLED`
- `PROXY_ROTATION_MODE`
- `PROXY_POOL`
- `PROXY_ROTATION_RETRY_LIMIT`
- `PROXY_BLACKLIST_TTL`
- `TASK_FAILURE_THRESHOLD`
- `TASK_FAILURE_PAUSE_SECONDS`
- `TASK_FAILURE_GUARD_PATH`

完整示例见 `.env.example`。

</details>

## Web 界面认证

<details>
<summary>点击展开认证说明</summary>

- Web UI 当前使用登录页收集账号密码，并通过 `POST /auth/status` 校验。
- 登录成功后，前端会在浏览器本地保存登录状态，用于路由守卫和 WebSocket 初始化。
- 默认账号密码为 `admin/admin123`，生产环境请务必修改。

</details>

## 🚀 工作流程

下图描述了单个监控任务从启动到完成的核心处理逻辑。主服务运行于 `src.app`，按用户操作或定时调度启动一个或多个任务进程。

```mermaid
graph TD
    A[启动监控任务] --> B[选择账号/代理配置];
    B --> C[任务: 搜索商品];
    C --> D{发现新商品?};
    D -- 是 --> E[抓取商品详情 & 卖家信息];
    E --> F[下载商品图片];
    F --> G[调用AI进行分析];
    G --> H{AI是否推荐?};
    H -- 是 --> I[发送通知];
    H -- 否 --> J[保存记录到 SQLite];
    I --> J;
    D -- 否 --> K[翻页/等待];
    K --> C;
    J --> C;
    C --> L{触发风控/异常?};
    L -- 是 --> M[账号/代理轮换并重试];
    M --> C;
```

## 常见问题

<details>
<summary>点击展开常见问题</summary>

### AI 任务创建为什么不是立即完成？

AI 模式会先生成分析标准，再创建任务。现在该流程已改为后台 job，提交后会显示独立进度弹窗，避免表单长时间卡住。

### 区域筛选为什么默认建议留空？

区域筛选会显著减少搜索结果，适合明确只看某个区域的场景。若你先验证整体市场，建议先不填。

### 本地页面打开后提示前端构建产物不存在？

说明根目录 `dist/` 缺失。可直接执行 `./start.sh`，或先在 `web-ui/` 里执行 `npm run build`，再确认构建产物已复制到仓库根目录。

### `./start.sh` 为什么提示缺少 Playwright 或浏览器？

这是脚本的前置检查。请先安装 Playwright CLI 与 Chromium，并确保系统中可用 Chrome / Edge（Linux 环境也可用 Chromium），然后重新执行 `./start.sh`。

</details>



## 致谢

<details>
<summary>点击展开致谢内容</summary>

本项目在开发过程中参考了以下优秀项目，特此感谢：

- [superboyyy/xianyu_spider](https://github.com/superboyyy/xianyu_spider)

以及感谢LinuxDo相关人员的脚本贡献

- [@jooooody](https://linux.do/u/jooooody/summary)

以及感谢 [LinuxDo](https://linux.do/) 社区。

以及感谢 ClaudeCode/Gemini/Codex 等模型工具，解放双手 体验Vibe Coding的快乐。

</details>


## 注意事项

<details>
<summary>点击展开注意事项详情</summary>

- 请遵守闲鱼的用户协议和robots.txt规则，不要进行过于频繁的请求，以免对服务器造成负担或导致账号被限制。
- 本项目仅供学习和技术研究使用，请勿用于非法用途。
- 本项目采用 [MIT 许可证](LICENSE) 发布，按"现状"提供，不提供任何形式的担保。
- 项目作者及贡献者不对因使用本软件而导致的任何直接、间接、附带或特殊的损害或损失承担责任。
- 如需了解更多详细信息，请查看 [免责声明](DISCLAIMER.md) 文件。

</details>

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=Usagi-org/ai-goofish-monitor&type=Date)](https://www.star-history.com/#Usagi-org/ai-goofish-monitor&Date)

![Alt](https://repobeats.axiom.co/api/embed/b40d8a112271b4bddabadd8fe2635be3c1aa28a3.svg "Repobeats analytics image")
