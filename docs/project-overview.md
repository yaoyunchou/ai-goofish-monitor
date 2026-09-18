# 项目说明文档（Project Overview）

> 本文档是 `ai-goofish-monitor`（闲鱼智能监控系统）的**全貌说明**，面向初次接触项目的读者，帮助你快速理解：这是一个什么样的项目、它解决什么问题、由哪些部分组成、核心概念与数据流是什么。
>
> 更深入的内容请参阅：
> - [系统架构](./design/architecture.md) — 分层架构、模块设计、数据模型、并发模型
> - [功能文档](./features.md) — 前后端全部功能点、API 端点清单、配置项详解

---

## 一、项目定位

**ai-goofish-monitor 是一个基于 Playwright + AI 的闲鱼（Xianyu / Goofish）二手商品智能监控机器人。**

它解决的核心痛点是：在闲鱼海量的 C2C 商品中，**持续自动地找到"值得买"的二手好货**，并在第一时间通知你。

与普通爬虫 + 关键词过滤的方案不同，本项目引入 **AI 多模态分析**（文字 + 图片），让"什么值得买"的判断标准可以是一段自然语言描述（例如"MacBook Air M1，8G+256G，个人自用，无维修进水，价格低于 3000"），由 AI 自动生成分析标准并对每个商品进行图文深度分析，而不是只能靠死板的关键词。

### 核心能力一览

| 能力 | 说明 |
|------|------|
| 多任务并发监控 | 多个任务独立配置关键词、价格区间、筛选条件、AI 判定标准，可同时运行 |
| AI 图文分析 | 多模态大模型分析商品图片 + 文字，输出推荐/不推荐及理由 |
| 关键词规则判定 | 不依赖 AI 的轻量模式，命中关键词即推荐（OR 逻辑） |
| AI 品类过滤（门禁） | 在完整 AI 分析前先用轻量 AI 过滤明显非目标商品，节省成本 |
| 多渠道即时通知 | ntfy / 企业微信 / Bark / Telegram / Gotify / 通用 Webhook 六种渠道 |
| 定时调度 | Cron 表达式驱动周期性任务（APScheduler） |
| 账号与代理轮换 | 多账号（auto/fixed/rotate 策略）、代理池轮换与失败黑名单 |
| 失败熔断保护 | 连续失败自动暂停任务，避免登录态失效后无限重试触发风控 |
| 卖家画像采集 | 采集卖家昵称、芝麻信用、注册时长、好评率、在售/已售数据 |
| 价格历史与性价比洞察 | 记录价格快照，计算市场均价、历史低点、性价比评分 |
| 商品收录与 SKU 拉取 | 收藏感兴趣的商品，拉取全量 SKU 规格与分档价格 |
| Web 可视化管理 | 任务、账号、结果、日志、设置全在 Web UI 完成 |
| 结果黑名单 | 用关键词/正则隐藏误匹配的商品 |
| 数据导出 | 结果一键导出 CSV / NDJSON |
| 多语言 | Web UI 支持简体中文与英文 |
| Docker 一键部署 | 多架构（amd64/arm64）镜像，内置 Chromium |
| 卖家订阅 | 独立 CRUD + Cron；C 端主页采集；想要/浏览量追踪 |
| 店铺数据罗盘 | 卖家工作台 datacompass；1/7/30 天周期可视化 |

---

## 二、系统组成

整个系统由以下部分组成：

```
ai-goofish-monitor/
├── 后端服务（Python / FastAPI）        src/
│     ├── Web API 路由层                 src/api/routes/
│     ├── 业务服务层                     src/services/
│     ├── 领域模型与仓储接口             src/domain/
│     └── 基础设施层                     src/infrastructure/
├── 爬虫 CLI 入口                       spider_v2.py（被服务层以子进程方式调用）
├── 前端 Web UI（Vue 3 + Vite）         web-ui/
├── Chrome 登录态导出扩展               chrome-extension/
├── 部署与运维                          Dockerfile* / docker-compose* / start.sh / .github/
├── 数据库 Schema 与迁移脚本            supabase/ / scripts/
└── 文档与测试                          docs/ / tests/ / README.md
```

### 2.1 后端（FastAPI + Playwright）

后端是系统的大脑，采用**分层架构**（详见[架构文档](./design/architecture.md)）：

- **API 层** `src/api/routes/`：对外暴露 REST API 与 WebSocket
- **服务层** `src/services/`：业务逻辑（任务、进程、调度、AI、通知、结果、收藏等 28 个模块）
- **领域层** `src/domain/`：`Task` 实体、任务生成作业模型、`TaskRepository` 仓储接口
- **基础设施层** `src/infrastructure/`：数据库（PostgreSQL）、配置管理、AI 客户端、通知客户端

后端同时承担两件事：

1. **Web 服务**（`python -m src.app` 常驻）：提供 Web UI 的 API、管理任务与调度；
2. **爬虫执行**（`spider_v2.py`）：当任务被启动时，服务层以**子进程**方式拉起爬虫，爬虫内用 Playwright 模拟移动端浏览器访问闲鱼。

### 2.2 前端（Vue 3）

基于 Vue 3 + TypeScript + Vite + Tailwind CSS + shadcn-vue 风格的 SPA，提供 **13 个路由页面**（监控概览、任务、账号、结果、收藏详情、卖家订阅 5 页、店铺数据罗盘、日志、设置、登录）。通过 REST API 与 WebSocket 与后端实时交互。

### 2.3 Chrome 扩展（登录态导出）

`chrome-extension/` 是辅助工具：一键导出闲鱼的完整登录态（Cookie + 浏览器环境指纹 + 请求头），比手动复制 Cookie 更贴近真实浏览器、更不易触发风控。

### 2.4 数据库（PostgreSQL）

主数据存储于 PostgreSQL（兼容 Supabase）。核心表：`tasks`（任务）、`result_items`（结果）、`price_snapshots`（价格快照）、`collected_items`（收录）、`result_blacklist_rules`（黑名单）、`app_metadata`（元数据）。

---

## 三、技术栈

### 后端

| 技术 | 用途 |
|------|------|
| Python 3.10+ | 开发语言 |
| FastAPI | Web 框架（提供 REST API + 静态资源 + WebSocket） |
| Uvicorn | ASGI 服务器 |
| Playwright | 浏览器自动化，模拟移动端访问闲鱼 |
| APScheduler | Cron 定时调度 |
| OpenAI SDK | OpenAI 兼容接口的 AI 调用 |
| cursor-sdk | Cursor SDK 作为备选 AI 提供方 |
| psycopg 3 | PostgreSQL 驱动 |
| Pydantic / pydantic-settings | 数据校验与类型安全配置 |
| python-dotenv | `.env` 环境变量加载 |
| httpx / requests / python-socks | HTTP 客户端与代理支持 |
| Pillow / pyzbar / qrcode | 图片处理与二维码 |
| aiofiles | 异步文件读写 |

### 前端

| 技术 | 用途 |
|------|------|
| Vue 3.5 + TypeScript | 框架 |
| Vite 7 | 构建工具 |
| Vue Router 4 | 前端路由（History 模式） |
| Tailwind CSS 3 | 样式 |
| shadcn-vue + reka-ui | UI 组件库（本地手工构建） |
| vue-i18n | 国际化（中/英） |
| @vueuse/core | 组合式工具集 |
| lucide-vue-next | 图标 |

### 基础设施

- PostgreSQL 16（生产 / Supabase 或自建）
- Docker + Docker Compose（多架构镜像）
- GitHub Actions（CI/CD：镜像构建与发布、AI 机器人）
- Nginx（可选的前端独立部署）

---

## 四、目录结构详解

### 4.1 根目录

| 路径 | 说明 |
|------|------|
| `src/` | 后端源码 |
| `spider_v2.py` | 爬虫 CLI 入口 |
| `web-ui/` | 前端源码 |
| `dist/` | 前端构建产物（由 `web-ui` 构建后复制到根目录，后端直接托管） |
| `docs/` | 文档 |
| `tests/` | 测试 |
| `chrome-extension/` | Chrome 扩展 |
| `supabase/` | 数据库 Schema / 迁移 SQL |
| `scripts/` | 运维脚本（数据库验证、迁移、环境检查） |
| `prompts/` | AI 提示词文件（`base_prompt.txt` 基础提示词、`*_criteria.txt` 各任务判定标准） |
| `state/` | 闲鱼登录态 JSON 文件（多账号） |
| `logs/` | 运行日志、AI 分析日志、失败保护状态文件 |
| `images/` | 商品图片缓存（含任务临时图片目录） |
| `jsonl/` | 爬虫历史 JSONL 输出（bootstrap 导入源） |
| `price_history/` | 历史价格快照文件（bootstrap 导入源） |
| `static/` | 静态资源（截图等） |
| `config.json` / `config.json.example` | 旧版 JSON 任务配置 |
| `.env` / `.env.example` | 环境变量配置 |
| `Dockerfile` / `Dockerfile.base` / `Dockerfile.release` | 镜像构建文件 |
| `docker-compose.yaml` / `.dev.yaml` / `.dev.yml` | 部署编排 |
| `start.sh` | 一键启动脚本 |
| `desktop_launcher.py` | 桌面端打包启动器（PyInstaller） |
| `run_live_smoke.sh` | 真实流量冒烟测试脚本 |
| `CLAUDE.md` / `AGENTS.md` | AI 助手与贡献者指南 |
| `log.md` | 项目变更日志 |

### 4.2 后端 `src/`

| 路径 | 说明 |
|------|------|
| `src/app.py` | FastAPI 应用入口，生命周期管理、路由注册、静态文件托管 |
| `src/scraper.py` | **爬虫核心**：搜索、筛选、翻页、详情、卖家采集全流程 |
| `src/ai_handler.py` | AI 商品分析（图片下载、消息组装、调用、验证、重试） |
| `src/ai_message_builder.py` | AI 消息/文本 Prompt 构建 |
| `src/item_detail_parser.py` | 商品详情 API → SKU 解析 |
| `src/keyword_rule_engine.py` | 关键词规则判定引擎 |
| `src/parsers.py` | 搜索结果、用户主页、评价等 API 响应解析 |
| `src/search_response_utils.py` | 搜索 MTOP 响应解包与诊断 |
| `src/rotation.py` | 账号/代理轮换池（黑名单 TTL） |
| `src/failure_guard.py` | 失败熔断保护器 |
| `src/prompt_utils.py` | AI 生成分析标准（criteria） |
| `src/config.py` | 遗留兼容配置层 |
| `src/utils.py` | 通用工具 |
| `src/api/routes/` | 10 个路由模块（accounts/collections/dashboard/login_state/logs/prompts/results/settings/tasks/websocket） |
| `src/api/dependencies.py` | FastAPI 依赖注入 |
| `src/services/` | 28 个业务服务模块 |
| `src/domain/` | 领域模型（Task 实体、生成作业）+ 仓储接口 |
| `src/infrastructure/config/` | 配置管理（Pydantic settings + env_manager + 运行时状态） |
| `src/infrastructure/persistence/` | 数据库连接、任务仓储（PG）、SQL 方言、存储引导 |
| `src/infrastructure/external/` | AI 客户端、Cursor 传输、6 个通知渠道客户端 |
| `src/core/cron_utils.py` | Cron 表达式构建 |

### 4.3 前端 `web-ui/src/`

| 路径 | 说明 |
|------|------|
| `views/` | 8 个页面视图 |
| `components/` | 业务组件（tasks/results/settings/layout）+ UI 基础组件（shadcn-vue） |
| `composables/` | 9 个组合式函数（状态管理） |
| `api/` | 8 个 API 调用模块 |
| `services/websocket.ts` | WebSocket 客户端 |
| `lib/` | HTTP 封装、工具函数、任务表单查询 |
| `types/` | TypeScript 类型定义 |
| `i18n/` | 中英文翻译 |
| `data/goofishRegions.json` | 闲鱼省市区数据 |

---

## 五、核心概念

### 5.1 任务（Task）

任务是监控的最小单元。一个任务定义了一次"持续搜索并分析某类商品"的完整行为：

| 维度 | 字段示例 |
|------|----------|
| 搜什么 | `keyword`（搜索关键词） |
| 怎么筛 | `min_price` / `max_price` / `personal_only`（仅个人闲置）/ `free_shipping`（包邮）/ `new_publish_option`（新发布）/ `region`（省市区三级） |
| 抓多少 | `max_pages`（最多翻页数） |
| 怎么判 | `decision_mode`：`ai`（AI 图文分析）/ `keyword`（关键词规则） |
| 判断依据 | `description`（AI 模式购买需求）、`keyword_rules`（关键词模式规则） |
| 用什么账号 | `account_strategy`：`auto` / `fixed` / `rotate` |
| 何时跑 | `cron`（Cron 表达式，空则为手动触发） |
| 辅助 | `analyze_images`（是否分析图片） |

### 5.2 判定模式（decision_mode）

- **AI 模式**：系统先用 AI 根据 `description` 生成一份"分析标准"（存到 `prompts/{keyword}_criteria.txt`），之后每个商品（含图片）都交给多模态大模型，按标准输出 `is_recommended` / `reason` / `risk_tags` / `criteria_analysis`。
- **关键词模式**：纯规则引擎，把商品标题、描述等所有文本与关键词列表做匹配（OR 逻辑），命中即推荐。轻量、零成本、无需 AI。

### 5.3 账号与登录态

- 登录态以 JSON 文件保存在 `state/` 目录（每账号一个文件），可通过 Web UI 或 Chrome 扩展导入。
- 每个任务可以绑定账号（`fixed`）、在账号池中轮换（`rotate`）或自动选择（`auto`）。
- 登录态失效时爬虫会检测并抛出 `LoginRequiredError`，失败保护机制会自动暂停任务、触发通知，待更新 Cookie 后自动恢复。

### 5.4 结果（Result）

爬虫抓取的每条商品记录会写入 `result_items` 表，包含商品信息、卖家信息、AI 分析、价格洞察四大部分。结果以**关键词**为维度组织成"结果文件"（`{keyword}_full_data.jsonl` 为文件名标识）。

### 5.5 推荐链路（推荐 → 通知 → 存储）

商品判定为"推荐"后：保存记录 → 发送多渠道通知 → 结果可在 Web UI 查看、导出。

---

## 六、数据流总览

### 6.1 任务运行主流程

```
用户创建任务（Web UI / API / config.json）
        │
        ▼
   SchedulerService 按 cron 触发 或 手动启动
        │
        ▼
   ProcessService 启动 spider_v2.py 子进程（每任务一个进程）
        │
        ▼
   scraper.py: scrape_xianyu() 单任务抓取生命周期
        │
        ▼
   ┌──────────────────────────────────────────────┐
   │ 1. 初始化：加载账号/代理轮换池、已处理去重集  │
   │ 2. 失败保护检查：连续失败则暂停               │
   │ 3. 启动 Playwright（移动端模拟 + 反检测）     │
   │ 4. 搜索：goofish.com/search?q=keyword         │
   │ 5. 筛选：新发布/个人闲置/包邮/区域/价格       │
   │ 6. 分页遍历 1..max_pages                      │
   │ 7. 每条新商品：详情页 → 卖家信息 → 图片       │
   │ 8. 提交 ItemAnalysisDispatcher 异步分析       │
   │ 9. 翻页 / 页间休息                           │
   │10. 等待所有分析完成，清理临时图片             │
   │11. 成功/失败上报 FailureGuard                 │
   └──────────────────────────────────────────────┘
```

### 6.2 单条商品分析链路（多层判定）

```
商品记录
  │
  ├─ 1. 加载卖家画像（昵称/芝麻信用/注册时长/好评率，带缓存）
  ├─ 2. 判定链（顺序短路）：
  │     a. 关键词模式 → keyword_rule_engine 命中即推荐
  │     b. 启发式过滤 → 纯规则预检（如"仅数据线"直接剔除）
  │     c. AI 品类过滤 → 轻量 AI 判断是否目标品类（最多 2 张图）
  │     d. 完整 AI 分析 → 下载全部图片 → 多模态大模型 → 推荐/不推荐
  │     e. SKIP_AI_ANALYSIS → 全部视为推荐
  ├─ 3. 保存结果（result_items 表）+ 记录价格快照
  └─ 4. 若推荐 → 并发发送多渠道通知
```

### 6.3 Web 交互链路

```
浏览器（Vue 3 SPA）
  │  REST API（/api/*）＋ WebSocket（/ws）
  ▼
FastAPI 后端
  │
  ├─ 任务管理 API → TaskService → TaskRepository（PostgreSQL）
  ├─ 启动/停止 → ProcessService → spider_v2.py 子进程
  ├─ 结果/收藏 API → result_storage_service / collection_service
  ├─ 设置 API → env_manager / settings.py（写回 .env）
  └─ 状态变化 → websocket.broadcast_message → 前端实时刷新
```

---

## 七、项目发展历程

从项目 `log.md` 整理的演进轨迹：

| 时间 | 里程碑 |
|------|--------|
| ~2026-07-28 | 新增 docs 文档目录；支持 **Cursor SDK** 作为 AI 提供方（`AI_PROVIDER` 切换） |
| 2026-07-30 | 适配 cursor-sdk 1.0.26 桥接调用 |
| 2026-08-03 | 引入 **PostgreSQL**（Supabase/psycopg）；新增 **AI 品类过滤门禁**（listing_ai_filter）；新增**商品收录 + SKU 拉取** |
| 2026-08-04 | 修复搜索 resultList 解析；支持 **decision_mode=keyword** 关键词模式；Cookie 登录态管理完善 |
| 2026-08-05 | 新增本地 Postgres dev compose；完成 SQLite → Postgres 迁移 |
| 2026-09-09 | 本机（无 Docker）基于 Supabase 启动验证通过；Vite 7 构建升级 |
| 2026-09-15 | VS Code 调试配置优化（移除 reload 模式） |

**关键技术演进主线**：
1. SQLite → **PostgreSQL 单库**（彻底移除运行时 SQLite）
2. 纯 OpenAI → **OpenAI 兼容 + Cursor 双提供方**
3. 纯关键词 → **AI 图文分析 → AI 品类过滤 + AI 分析 双层 AI 判定**
4. 单账号 → **多账号策略（auto/fixed/rotate）+ 代理轮换**
5. 简单列表 → **完整 Web 管理 + 收录/SKU + 价格洞察 + 失败熔断**

---

## 八、快速上手

```bash
# 1. 克隆并准备环境
git clone <仓库地址> && cd ai-goofish-monitor
cp .env.example .env          # 编辑：配置 DATABASE_URL 与 AI_PROVIDER

# 2. 本地一键启动（自动装依赖、构建前端、启动后端）
./start.sh

# 3. 或 Docker 部署
docker compose up -d

# 4. 访问 http://localhost:8000 （默认账号 admin / admin123）
#    → 导入闲鱼登录态（Web UI「闲鱼账号管理」）
#    → 创建任务并启动
```

详细安装、配置与日常使用，见 [用户使用指南](./user-guide.md)。

---

## 九、与其它文档的关系

| 文档 | 内容 |
|------|------|
| **本文档** | 项目全貌、技术栈、目录、核心概念、数据流、发展历程 |
| [架构文档](./design/architecture.md) | 分层架构、模块职责、数据模型、并发与进程模型、配置体系、设计决策 |
| [功能文档](./features.md) | 前后端功能点清单、API 端点表、任务配置、通知渠道、命令行、测试 |
| [用户使用指南](./user-guide.md) | 安装、配置、日常使用（面向使用者） |
| [AI 提供方配置](./ai-provider.md) | OpenAI 兼容接口与 Cursor SDK 切换 |
| [闲鱼 Cookie 获取指南](./getting-xianyu-cookies.md) | 登录态获取与导入 |
| [数据库接入指南](./design/database-supabase-integration.md) | Supabase/PostgreSQL 接入 |
