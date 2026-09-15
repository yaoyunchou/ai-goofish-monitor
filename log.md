# 变更日志

## 2026-09-15

### fix(seller-subscription): 主页头部超时不再阻断商品列表 + 采集状态展示

- `scrape_user_profile` 头部 API 失败时继续滚动抓 `item.list`；加强滚动与登录态提示
- 仅在有商品入库时更新 `last_captured_at`；调度表记录 `last_run_summary` / 入库条数
- 前端采集后轮询状态，展示上次采集结果横幅

### feat(seller-subscription): 详情采集分批模拟访问策略

- 新增 `seller_subscription_pacing`：详情间隔 4–8s、每 10 条批休 60–120s、切换卖家休 2–5 分钟、每 25 条长暂停
- 卖家内商品顺序随机打乱；启动时打印预计总耗时
- 调度表支持 `pacing_json` 覆盖默认节奏（可选）

### fix(seller-subscription): 添加卖家 POST 422

- `sellerSubscriptions.ts` 的 POST/PATCH 请求补上 `Content-Type: application/json`，修复 FastAPI 无法解析 body 导致 422

### feat(seller-subscription): 独立订阅管理，与任务管理解耦

- 新增 `seller_subscriptions` / `seller_subscription_schedule` 表，卖家在「卖家订阅」页直接添加
- API：`GET/POST/PATCH/DELETE /api/seller-subscriptions`、`PATCH /schedule`、`POST /run`
- 定时采集走独立调度任务（`spider_v2.py --seller-subscriptions`），不再依赖 `seller_subscription` 任务类型
- 任务列表 API 与任务表单隐藏卖家订阅类型；启动时自动迁移旧订阅任务中的卖家
- `SellerSubscriptionView` 重写：订阅卖家表 + 调度配置 + 商品指标表

### fix(tasks): 删除任务幂等 + 防重复提交

- `DELETE /api/tasks/{id}` 任务已不存在时仍返回 200，避免连点确认报 404
- 删除前 `stop_task(quiet=True)`，不再刷「没有正在运行的进程」
- 任务删除对话框增加 `isDeleteSubmitting`，防止重复点击

### refactor(subscription): 固定监控每位卖家前 100 条在售商品

- `seller_subscription_scraper` 移除列表侧「想要/浏览量」过滤，改为每位卖家拉取前 100 条在售商品并逐条详情入库
- `scrape_user_profile` 新增 `max_items`，列表滚动到足够条数即停止，避免全量翻页
- 默认 cron 改为每天 `0 8 * * *`；任务配置可传 `item_limit` 覆盖默认 100
- 前端任务表单提示文案同步更新

### feat(subscription): 用户页订阅与卖家工作台数据罗盘

- 新增任务类型 `seller_subscription` / `shop_datacompass`，支持批量粘贴用户主页链接
- 订阅采集走商品详情 API 补抓想要/浏览量，写入 `seller_item_metrics` 时序表
- 新增卖家画像/指标表与 datacompass 快照表，Web UI 增加「卖家订阅」「店铺数据」页面
- 店铺数据直接解析已探索的 `mtop.alibaba.idle.seller.pc.datacompass.*` API（1d/7d/30d）
- 修复 Postgres 命名参数适配误替换 `'[]'::jsonb`，避免 dashboard / schema 启动 500

### docs(exploration): 闲鱼用户主页与卖家工作台页面探索

- 新增 `scripts/explore_goofish_pages.py`：Playwright 探索脚本，拦截 MTOP API 并输出 DOM/截图快照
- 新增 `docs/exploration/personal-profile-exploration.md`：C 端用户主页（`userId=2221197154547`）结构、API 字段、与 `scrape_user_profile` 对齐的采集流程
- 新增 `docs/exploration/seller-workbench-exploration.md`：卖家工作台「数据总览」路由、datacompass 系列 API、近 1 天经营指标样本
- 探索产物：`docs/exploration/snapshots/exploration_snapshot.json`、`personal_profile.png`、`seller_workbench.png`
- 更新 `docs/README.md` 索引，补充页面探索文档入口

### fix(dev): /api 请求不再误返回 index.html

- `src/app.py` catch-all 对未匹配的 `/api/*` 返回 JSON 404，避免旧后端或路由缺失时 curl 拿到 HTML
- `web-ui/vite.config.ts` 代理后端失败时返回 JSON 502（后端未启动），不再回落到 Vite 的 SPA 页面

### test(shop-analytics): 集成测试验证接口始终返回 JSON

- 新增 `tests/integration/test_api_shop_analytics.py`：覆盖 overview / distribution / trend 空数据与有数据、未知路由 404 非 HTML
- 本地 `pytest tests/integration/test_api_shop_analytics.py --capture=no` 全部通过 → **后端接口正常**

### fix(shop-analytics): 无数据返回 200 JSON，前端不再解析 HTML 报错

- `overview` / `distribution` / `trend` 无快照时返回 `has_data: false` + `empty_message`（200），避免前端 `response.json()` 与业务 404 混淆
- `web-ui/src/lib/http.ts` 检测 HTML 响应并提示「后端未启动」，修复 `Unexpected token '<'`
- `ShopAnalyticsView` 根据 `has_data` 展示空状态横幅

### fix(logging): HTTPException 404 不再刷整段 traceback

- `src/app.py` 业务 404 改为一行 stderr 输出，避免 debugpy 下 `logging` emit 失败把正常响应打成崩溃堆栈

### fix(logging): debugpy 下调试日志不再掩盖 API 异常

- 新增 `src/infrastructure/logging_config.py`：uvicorn 日志统一写入 stderr，修复 `underlying buffer has been detached`
- `src/app.py` 在 lifespan 与应用入口应用该配置，并增加 `HTTPException` 一行式告警日志（如 `POST /api/shop-analytics/collect -> 404: 未找到已启用的店铺数据罗盘任务`）

### chore(vscode): 后端 FastAPI 调试配置

- 更新 `.vscode/launch.json`：`Backend: FastAPI (推荐)` 无 reload，可正常 spawn 爬虫子进程
- 新增 `Backend: src.app`（等价 `python -m src.app`，端口读 `.env` 的 `SERVER_PORT`）
- 移除 `Backend: FastAPI (reload)`：Windows + debugpy 下 reload 会导致任务启动 500 与日志 buffer detached

## 2026-09-09

### chore(dev): 本机启动 Web 服务

- 本机无 Docker / 本地 Postgres，使用已有 Supabase `goodfish`（`DATABASE_URL` 来自 gitignore 的 `.env`，未入库）
- 安装缺失 Python 依赖（`psycopg` 等），`python -m scripts.verify_database` 通过
- 使用 Node 22 完成 `web-ui` 生产构建（当前 PATH 默认 Node 18 不满足 Vite 7）
- 后端 `python -m src.app` 已监听 `http://127.0.0.1:8000`，`/health` 与登录校验通过

## 2026-08-05

### chore(dev): 本地一键 PostgreSQL + 前端构建

- 新增 `docker-compose.dev.yml`：本机 Postgres 16，首次启动自动执行 `supabase/migrations/20260803120000_initial_goofish_schema.sql`
- 从 `.env.example` 生成 `.env`，`DATABASE_URL` 指向 `127.0.0.1:5432/goofish`（与 compose 默认账号一致）
- 完成 `pip install -r requirements.txt`、`playwright install chromium`、`web-ui` 生产构建（产物在根目录 `dist/`）

## 2026-08-04

### chore(ops): 更新账号 user_874979280（蓝小飞鱼）登录态

- 自 Cookie 请求头导入并覆盖 `state/user_874979280.json`（多域名展开）

### fix(scraper): 搜索 resultList 解析与响应选择

- 支持 MTOP `data` 为 JSON 字符串时解包 `resultList`（此前只读 `data.resultList` 对象形式）
- 筛选后优先选用 **非空** 的 initial/final 搜索响应，避免「个人闲置」等把有效首屏数据覆盖为空
- 首屏与筛选均无列表时滚动触发一次搜索 API 重试
- 空列表时输出 `[搜索诊断]`（ret、data_keys、resultList 长度）；`AI_DEBUG_MODE=true` 仍打印完整 JSON
- 个人闲置筛选超时/失败时回退首屏响应，不再直接中断


- `decision_mode=keyword`，搜索词为「天才知音全新儿童故事机早教机智能学习机随身听」
- 匹配规则：`天才知音`、`故事机`（标题命中即关键词推荐，不走 AI 看图）
- 绑定账号 `state/xy699909515578.json`，cron 每 2 小时，`task id=1`

### chore(ops): 刷新闲鱼 Cookie 登录态

- 更新 `state/xy699909515578.json`（多域名 `.goofish.com` / `.taobao.com` 展开，便于 Playwright 携带）
- 任务「机乐堂30w多口充电头」重新绑定 `account_strategy=fixed`
- 验证：搜索页可解析商品列表；此前 02:00 失败为旧 Cookie 跳转登录页

### chore(release): 合并 Postgres-only 与配置修复到 `master`

- 将 `cursor/remove-sqlite-postgres-only-dc12` fast-forward 合入 `origin/master`（含 #6 / #7 对应改动）
- 从仓库删除误提交的 `.env.20260803` / `.env.20260804`，并忽略 `.env.202608*`
- 已关闭重复 PR #9（与 master 实现路径冲突，内容已由 dc12 分支覆盖）

### chore(tasks): 新增监控任务「机乐堂30w多口充电头」

- 通过 API 写入 Supabase `tasks` 表（AI 判定、看图、价格 30–150、cron 每 2 小时）
- 新增 `prompts/机乐堂_30w多口充电头_criteria.txt`

### chore(docs): 全面去除 SQLite 文档与配置残留

- README / README_EN / user-guide / AGENTS / database-supabase-integration 统一为仅 PostgreSQL
- `.env` 示例与备份注释去掉 `DATABASE_DRIVER`、`APP_DATABASE_FILE`
- `storage_names` 重命名为 `LEGACY_SQLITE_MIGRATION_SOURCE`（仅迁移脚本）
- live 测试不再注入 `APP_DATABASE_FILE`
- MySQL 迁移计划文档标注为归档参考

### feat(db): SQLite → Postgres 迁移 CLI + 运行时仅 Postgres

- 新增 `python3 -m scripts.migrate_sqlite_to_postgres`（保留 tasks/result_items 等主键 id）
- 移除运行时 SQLite：`db_connection` 仅连 `DATABASE_URL`；删除 `sqlite_connection` 等
- 测试任务 API 使用 `InMemoryTaskRepository`，不连真实库
- `.env.example` 仅保留 `DATABASE_URL`

### fix(config): 数据库配置与 env_manager 统一（.env 优先于 Secrets）

- `database_config` 的 `DATABASE_DRIVER` / `DATABASE_URL` / `APP_DATABASE_FILE` 改为经 `env_manager.get_value` 解析，与 Web 设置、系统状态一致
- `verify_database` 输出配置来源；密码失败与 IPv6 分开展示提示
- `EnvManager.config_source()` 供运行时诊断
- 测试使用 `data/.pytest-env`，避免仓库 `.env` 干扰
- 本地可保留 `.env` 备份文件，但勿提交 Git（已加入 `.env.202608*` 忽略规则）

## 2026-08-03

### feat(db): DATABASE_DRIVER=postgres（Supabase / psycopg）

- 新增 `database_config`、`db_connection`、`sql_dialect`、`storage_bootstrap`
- 任务/结果/收录/行情读写统一走 `db_connection()`，Postgres 使用 `ON CONFLICT` 方言
- 依赖：`psycopg[binary]>=3.1.18`
- 测试环境强制 `DATABASE_DRIVER=sqlite`
- 验证脚本：`python3 -m scripts.verify_database`

- `docs/database-supabase-integration.md`（项目 wkhatdhgohkpsqkytotz 连接串与 checklist）
- `supabase/migrations/20260803120000_initial_goofish_schema.sql`
- `.env.example` 增加 `DATABASE_DRIVER` / `DATABASE_URL`

### docs: SQLite → MySQL 迁移计划

- 新增 `docs/database-mysql-migration-plan.md`（现状盘点、分阶段 A～E、DDL/测试/风险 checklist）

### feat(scraper): 分析代理增加统一 AI 品类过滤（门禁）

- 新增 `src/services/listing_ai_filter.py` 与 `prompts/listing_ai_filter_system.txt`
- `ItemAnalysisDispatcher` 在关键词/完整 AI 分析前执行过滤，剔除「仅数据线」等非目标品类（`analysis_source=ai_filter`）
- 环境变量 `AI_LISTING_FILTER_ENABLED`（默认 `true`）；任务级可用 `enable_ai_listing_filter` 覆盖
- 购买意图取自任务 `description`（空则回退搜索 `keyword`）；过滤阶段最多下载 2 张图辅助识别

### feat(collections): 收录商品并拉取全量 SKU 价格

- `src/services/collection_service.py`、`item_sku_fetch_service.py`、`parsers/item_detail_parser.py`
- API：`/api/collections`（收录、详情、刷新 SKU）
- 结果列表项附带 `_result_item_id` 字段

## 2026-07-31

### chore(tasks): 机乐堂 30W 任务改为 AI 判定并补充 criteria

- 任务「机乐堂30W充电头」由关键词 OR 模式改为 `decision_mode=ai`，启用看图分析
- 新增 `prompts/机乐堂_30w_充电头_criteria.txt`（品牌一票否决、排除卡斐乐等非机乐堂）
- 结果集 `机乐堂_30w_充电头_full_data.jsonl` 配置展示黑名单关键词，便于结果页过滤误匹配

## 2026-08-04

### chore(ops): 导入闲鱼 Cookie 至账号管理

- 将用户提供的 Cookie 请求头转换为 Playwright `cookies` JSON，写入 `state/xy699909515578.json`（账号名取自 `tracknick`）
- 任务「机乐堂30w多口充电头」已绑定 `account_strategy=fixed` 与上述登录态文件
- 临时导入文件已删除；`state/` 仍在 `.gitignore`，不会进入版本库

## 2026-07-30

### fix(ai): 适配 cursor-sdk 1.0.26 AsyncClient 桥接调用

- `cursor_transport` 通过 `AsyncClient.launch_bridge` + `AsyncAgent.prompt(..., client=)` 调用
- 单元测试 mock 同步更新


- 基于 `origin/cursor/cursor-sdk-integration-d454` 继续开发（工作分支 `cursor/sync-cursor-sdk-dc12`）
- `AISettings.effective_cursor_runtime()`：`CURSOR_RUNTIME` 留空且在 `CURSOR_AGENT=1` 时自动使用 `cloud`
- `cursor_transport`：cloud 模式在未配置 `CURSOR_CLOUD_REPOS` 时从 `git remote.origin.url` 推断仓库
- `.env.example`：`CURSOR_RUNTIME` 默认留空并补充说明；`docs/ai-provider.md`、`AGENTS.md` 更新
- 设置 API 返回 `CURSOR_RUNTIME_EFFECTIVE`；补充单元测试

## 2026-07-28

### docs: 新增 docs 目录与详细使用文档

- 新增 `docs/user-guide.md` 用户使用指南
- 新增 `docs/getting-xianyu-cookies.md`（含 F12 手动获取 Cookie 步骤与项目导入方式）
- 新增 `docs/ai-provider.md`（OpenAI 兼容接口与 Cursor SDK 配置、迁移、技术说明）
- README 增加文档索引链接

### feat(ai): 支持 Cursor SDK 作为 AI 提供方

- 新增 `AI_PROVIDER` 配置，支持 `openai`（默认）与 `cursor`
- 新增 `src/infrastructure/external/cursor_transport.py`，通过 Cursor Python SDK 的 `AsyncAgent.prompt()` 完成文本/图片分析
- `AIClient`、`ai_handler`、设置 API 与 Web UI 已接入 Cursor 配置项
- 依赖新增 `cursor-sdk`
