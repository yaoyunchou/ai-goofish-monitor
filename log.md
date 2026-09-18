# 变更日志

## 2026-09-18

### fix(seller-subscription): 日志显式报告「整店跳过」，并澄清每店独立配额

- 背景：一次运行 2 个卖家只入库了 1 个，但结尾只打印 `扫描 N → 详情 N → 入库 N → 跳过 0`，被 `continue` 掉的店铺不进任何分母，看起来「一切正常」，极易误判为「只跑了一个店」
- `seller_subscription_scraper.py`：主页无在售商品而 `continue` 的店铺记入 `skipped_sellers`；结尾新增 `[店铺汇总] 订阅 N 家 → 有商品入库 M 家 → 整店跳过 K 家` + 逐店原因
- `seller_subscription_pacing.py`：`log_plan` 文案 `N 个卖家 × 最多 M 条/卖家` → `N 个卖家，每店最多 M 条（各店独立配额，互不占用）`，避免 `×` 被误读为配额共享
- 补测：`test_scrape_reports_whole_skipped_seller_in_summary`（整店跳过的汇总输出回归）；`tests -k "seller_subscription or pacing"` **49 passed**

### fix(seller-subscription): reload_jobs 不再卸掉卖家订阅定时任务

- `SchedulerService.reload_jobs` 只移除 `task_*` job，保留 `seller_subscriptions`
- `/api/seller-subscriptions/stats`（及调度 PATCH）返回进程内真实 `next_run_at`；job 未挂上为 null
- 采集控制台调度卡片展示「下次执行」，enabled 但无 next_run_at 时提示保存调度或重启后端

## 2026-09-17

### test(shop-analytics): QA 看板 T01–T05 补测与回归

- 后端补：非法 period 422（含旧 cycle `1d`）、dashboard 默认 today、空表 trend 7 个 null、7d 区间无锚点 want/view 为 null 非 0
- 前端补：`ShopAnalyticsView` 静态验收（只打 dashboard、空态 CTA、无 showPv 卡片、SVG 趋势）；`WantViewTrendChart` 全量 X 轴 + 空心日无圆点
- 锁定期望：`tooltipItems` 不得写死验收样本 185，应写「不是全库跨日去重商品数」（当前源码仍写死 185，单测红）
- 必跑：`pytest` 指定 4 文件 **27 passed**；`web-ui npm test` **18 passed / 1 failed**（i18n 185）

### feat(shop-analytics): 订阅日指标看板

- `/shop-analytics` 整页改为卖家订阅分析：四张卡片 + 近 7 日空心趋势图 + 店铺排行 + 热门 Top10
- 新接口 `GET /api/shop-analytics/dashboard?period=today|7d`，SQL 聚合 `seller_item_daily_metrics`；主页面不再打 overview/collect
- 空态引导采集控制台；侧栏仍为「店铺数据」；旧 datacompass 接口保留；商品数 tooltip 去掉写死的 185

### docs(design): 卖家订阅采集优先级 SSOT

- 新增 `docs/design/seller-subscription-collection-strategy.md`：现行三阶段、排序键、变更流程（先改文档再改代码再补测试）
- 索引：`docs/design/README.md`、`docs/prd/README.md`；`seller-subscription-scrape.md` §1.1 指向 SSOT，避免两套规则

### test(seller-subscription): 三阶段策略独立用例文件

- 新增 `tests/unit/test_seller_subscription_priority_strategy.py`（13 条），用例名直接对应策略：阶段零短预热、新店优先、阶段一/二队列
- 覆盖：`before_list_alignment` 不用 `before_seller` 长冷却；`last_captured_at` 空店在对齐与详情都排最前；今日无指标先于已有指标
- 回归：`pytest tests/unit/test_seller_subscription_priority_strategy.py tests/unit/test_seller_subscription_scraper.py tests/unit/test_seller_subscription_pacing.py -q` → **26 passed**

### feat(seller-subscription): 先对齐全部订阅店列表，无历史商品店优先

- 阶段零只拉各店主页商品列表，店间只用 3–6s 预热，不再套用 2–5 分钟「切换卖家」冷却
- 从未成功采集过的店铺（`last_captured_at` 为空）在列表对齐和详情阶段都排最前
- 阶段一：所有店「今日无数据」商品；阶段二：再更新「今日已有」商品
- 测试：`test_prioritize_sellers_never_captured_beats_missing_count`、`test_scrape_never_captured_shop_before_old_shop_even_if_fewer_missing`

### fix(seller-subscription): 卖家画像 1.1w 计数导致采集崩溃

- `parse_metric_int` 支持 `1.1w` / `1.2万` / `3k` 等缩写；`save_seller_profile` 对粉丝/商品数/评价数统一解析后再入库
- 修复前采集在保存第二家卖家画像时抛 `invalid input syntax for type integer: "1.1w"`，导致无新数据且 `is_running` 卡住

### feat(seller-subscription): Web 日志 + 跨卖家今日未采集优先

- 日志 API 支持 `task_id=-1`（`logs/seller_subscriptions_-1.log`）；日志页下拉增加「卖家订阅采集」
- `.env` 开关 `SELLER_SUBSCRIPTION_CONSOLE_LOG=true` 时，采集控制台内嵌实时日志面板（默认关闭）
- 采集策略改为全局两阶段：所有卖家「今日未采集」完成后，再统一「更新已有今日指标」；新店铺（未采集多）排在阶段一最前
- 详情采集日志增加 `[今日未采集]` / `[更新已有]` 与卖家、商品 ID 前缀，便于观察进度
- 测试：`test_api_logs` seller job、`test_scrape_runs_new_seller_missing_before_old_seller_updates`、`test_prioritize_sellers_by_missing`

### fix(seller-collection): 采集中状态/卖家数/无头回显

- `stats.is_running` 以 `ProcessService` 进程状态为准，返回页自动恢复轮询
- `seller_count` 改为订阅表总数（非已采集画像数）
- `run_headless` 允许 NULL（继承 `RUN_HEADLESS`）；调度弹窗回显与卡片展示逻辑一致

### fix(seller-subscription): 采集时间统一北京时间（Asia/Shanghai）

- 新增 `src/time_utils.py`；卖家订阅写入全部改用 `shanghai_now_iso()`（含爬取时间、last_captured、last_run）
- DB 连接默认 `SET TIME ZONE 'Asia/Shanghai'`；API 时间字段序列化为 `+08:00`
- 前端 `formatShanghaiTime` 固定按北京时间展示（`web-ui/src/lib/datetime.ts`）

### fix(seller-subscription): 卖家启用开关 + 今日未采集商品优先

- 前端 Switch 改为接收 `update:checked` 目标值，避免受控组件重复触发导致状态回弹
- 列表/详情页增加切换中防重入；后端列表与单条查询统一 `enabled` 布尔归一化
- 采集排序：查询当日已有 `seller_item_daily_metrics` 的商品，未采集优先、已采集随后（组内仍随机）
- 测试：`test_seller_subscription_pacing`、`test_seller_subscription_scraper`、集成 PATCH enabled 往返断言

### feat(seller-subscription): 日级去重 + 通用原始表 + 日指标 1:1

- 新表：`crawl_raw_records`（通用原始 JSON）、`seller_subscription_items`（静态主表）、`seller_item_daily_metrics`（日指标，`raw_record_id` UNIQUE FK）
- 采集写入改走 `upsert_seller_item_daily_snapshot` 同事务；卖家订阅路径停写 `result_items` / `seller_item_metrics` / `item_detail_api_raw`
- `seller_profiles` 按 `profile_day`（Asia/Shanghai）日级 UPSERT
- 列表/详情/趋势 API 优先读日级表，空时回退旧表；回填脚本 `scripts/backfill_seller_item_daily.py`
- 迁移：`supabase/migrations/20260917090000_seller_item_daily_schema.sql` + `ensure_incremental_schema`
- 单测：`tests/unit/test_seller_item_daily_storage.py`（4 passed）
- 文档：`docs/design/architecture.md`、`seller-subscription-scrape.md`、`features.md`、`database-supabase-integration.md`

### docs(design): 建立 docs/design 技术方案目录

- 迁入 `architecture.md`、`database-supabase-integration.md`、`database-mysql-migration-plan.md`
- 新增 `seller-subscription-scrape.md`（对应 PRD 的技术方案）
- 旧路径保留跳转；入口 `docs/design.md`；更新 README / AGENTS / software-company 约定

### docs(prd): 建立 docs/prd 目录并沉淀卖家订阅风控 PRD

- 新增 `docs/prd/README.md` 索引、`seller-subscription-anti-risk.md`（Plan 定稿 + 交付状态）
- 迁移 `docs/project-health-prd.md` → `docs/prd/project-health.md`，旧路径保留跳转
- 新增兼容入口 `docs/prd.md`；更新 `docs/README.md`、software-company SKILL/PM agent 路径约定

### fix(seller-subscription): 无头模式调度保存不持久化

- 启动时增量 DDL 补齐 `seller_subscription_schedule.run_headless` 列
- 前端 Switch 绑定修复；集成测试增加 PATCH 后 GET stats 断言

### feat(seller-subscription): 采集调度可配置无头模式（run_headless）

- 后端：`SellerSubscriptionScheduleUpdate.run_headless`；未配置时继承 `RUN_HEADLESS`
- API 响应增加 `run_headless_effective` 便于前端展示实际运行模式
- 前端：采集控制台调度弹窗与卡片展示无头/有头状态
- 测试：`tests/unit/test_seller_subscription_schedule.py`；集成 PATCH schedule 断言

### feat(web-ui): 阶段四前端文档 + Vitest smoke（9 passed）

- 新增 `web-ui/README.md`：技术栈、目录、开发/构建/测试命令、路由表
- Vitest + jsdom：`utils`、`goofish`、路由 smoke、i18n smoke 共 9 用例
- `vite.config.ts` 集成 test 配置；`package.json` 增加 `npm test` / `test:watch`
- CI：`.github/workflows/web-ui.yml`（Vitest + build，`web-ui/` 变更触发）
- `docs/user-guide.md` 卖家订阅/店铺罗盘章节补充探索截图引用
- 同步 `docs/features.md`、`tests/README.md`、`docs/project-health-prd.md`

## 2026-09-16

### test(project-health): 阶段三新模块测试补全（183 passed, 3 skipped）

**新增测试（18 用例）**
- `tests/unit/test_scheduler_service.py` — `reload_seller_subscription_job` 等 4 用例
- `tests/unit/test_scraper_shop_datacompass.py` — datacompass fixture 解析与 persist 4 用例
- `tests/unit/test_seller_subscription_scraper.py` — 入库过滤（想要+浏览量）、空配置 3 用例
- `tests/integration/test_api_accounts.py` — 2 用例
- `tests/integration/test_api_collections.py` — 3 用例
- `tests/integration/test_api_logs.py` — 2 用例
- `tests/fixtures/datacompass_seller_summary.json`、`datacompass_browse_summary.json`

**实现与隔离**
- `seller_subscription_scraper.py`：入库前 `has_want_and_view()` 过滤，与文档规则对齐
- 修复 `test_seller_subscription_scraper` 与 `test_cli_spider` 模块缓存冲突（`import_module` 回退）
- 更新 `tests/README.md`：186 可收集用例、accounts/collections/logs API 覆盖、阶段三清单

### fix(tests): 修复全部失败 pytest 用例（165 passed, 3 skipped）

- **实现修复**：`failure_guard.py` Windows 下先关闭文件再 `os.replace`；`result_storage_service.py` 兼容 Postgres JSONB 返回 `list` 的黑名单字段
- **测试适配 PostgreSQL 存储**：`test_api_results.py` 改为通过 `save_result_record` 写入数据库
- **AI 层重构**：`test_ai_handler_analysis.py` 改为 mock `AIClient._call_ai`
- **CLI 测试**：`test_cli_spider.py` 补全 fake scraper 导出并清理模块缓存
- **环境隔离**：`test_api_settings.py` 清理 `AI_PROVIDER`/`CURSOR_*`；`test_cursor_transport.py` 使用 `model_construct`
- **平台兼容**：`test_ai_client.py` 适配 Windows 环境变量大小写不敏感；`test_utils.py` 忽略 `_` 元数据字段
- **其他**：`test_app_lifespan.py` 补 mock 卖家订阅调度；`test_item_detail_parser.py`/`test_frontend_build_paths.py` 对齐当前实现

### fix(db): 已上线库自动补齐 item_detail_api_raw 表

- `ensure_schema` 对老库会因 bootstrap 标记提前返回，导致新表 DDL 未执行
- 新增 `ensure_incremental_schema()`，每次 `bootstrap_storage` 都跑幂等 `CREATE TABLE IF NOT EXISTS`

### feat(db): item_detail_api_raw 表归档详情 API 完整响应

- 新表 `item_detail_api_raw`：按 `item_id` + `task_name` 关联，存 `mtop.taobao.idle.pc.detail` 全量 JSON
- 卖家订阅采集成功时写入；`GET /api/seller-subscriptions/items/{id}/detail` 返回 `detail_api` 字段
- 迁移：`supabase/migrations/20260916170000_item_detail_api_raw.sql`
- 服务：`src/services/item_detail_raw_storage.py`

### chore(data): 导出卖家订阅爬虫原始 JSON 样例

- `data/seller_subscription_raw/item_1083008241172_raw_record.json` — 单商品爬虫原始 record
- `data/seller_subscription_raw/item_1083008241172_detail.json` — 含 metrics + summary 的完整 detail
- `data/seller_subscription_raw/seller_2222329704966_all_raw_records.json` — 该卖家已采集 6 条商品原始数据

### feat(seller-subscription): 商品详情 API 返回爬虫原始 JSON

- `GET /api/seller-subscriptions/items/{item_id}/detail` 从 `result_items` 读取完整 `raw_json` 并附带 `data_summary` 字段统计
- 前端详情页展示图片、描述与可复制的原始 JSON（取数测试）

### feat(web-ui): 卖家订阅商品详情页与闲鱼原页面跳转

- 商品列表行可点击，路由 `/seller-subscriptions/items/:itemId`
- 详情页展示快照指标与趋势图，「查看原页面」打开闲鱼商品页

### docs+test(project-health): 阶段一+二文档对齐与测试基线

**阶段一（文档）**
- 更新 `docs/features.md`：卖家订阅/店铺罗盘 UI、API §3.12–3.13、CLI、功能矩阵、测试 §13
- 更新 `docs/architecture.md`：新路由/服务/进程链路/数据表/前端 13 页
- 更新 `docs/user-guide.md`、`docs/project-overview.md`、`docs/database-supabase-integration.md`
- 修复 `README_EN.md`（PostgreSQL、新特性、去除乱码行）；`AGENTS.md` 补充 CI 与 PR 文档/测试要求

**阶段二（测试）**
- 修复全部失败用例（`failure_guard` Windows 锁、`result_storage` JSONB、测试与实现对齐等）→ **165 passed, 3 skipped**
- 新增 `.github/workflows/pytest.yml` CI 门禁
- `pyproject.toml` 默认 `--capture=no`（Windows 兼容）
- 重写 `tests/README.md`（168 用例、目录、CI、PR 检查清单）

### docs(project-health): software-company 项目健康度审计

- 主理人齐活林调度 PM + QA 完成现状审计：功能已完成但文档/测试严重滞后
- 新增 `docs/project-health-prd.md`：文档缺口 P0–P2、测试 22/164 失败、5 阶段整改计划
- 核心问题：卖家订阅/店铺罗盘未写入 features/architecture/user-guide；CI 无 pytest；6 个 API 零测试；前端零测试；`tests/README.md` 过时

### feat(cursor): 接入 software-company 多智能体团队配置

- 将 `software-company/` CodeBuddy 插件迁移为 Cursor 项目配置，便于本地测试 SOP 工作流
- 新增 `.cursor/agents/` 子代理 5 个：`software-team-lead`、`software-product-manager`、`software-architect`、`software-engineer`、`software-qa-engineer`
- 新增 `.cursor/skills/software-company/SKILL.md` 作为团队入口（`/software-company` 或 `/software-team-lead`）
- 协作机制适配：CodeBuddy `SendMessage`/`TeamCreate` → Cursor **Task** 子代理回传
- 工程师/QA 代理补充本项目约定（FastAPI 分层、`web-ui/` Vue 3、`pytest`）
- `software-company/README.md` 说明测试方式与差异

### fix(seller-subscription): 商品列表分页 SQL 占位符参数缺失

- `list_latest_item_metrics_paginated_sync` / `count_latest_item_metrics_sync` 执行时补上内层 `task_name`/`seller_user_id` 的 `params`，修复 `ProgrammingError: placeholders but N parameters were passed`
- **需重启后端**（`python -m src.app`）后生效；已验证 `GET /api/seller-subscriptions/items?seller_id=2222329704966` 正常返回 6 条商品

### chore(db): result_items MCP 导入完成（47/47）

- **uid 33 / id=27 修复完成**：MCP 顺序执行 `mcp_chunks_uid27/stmt_04`–`stmt_10`
  - chunk 4–8：staging `data_len` 6000 → **31394**；`jsonb_typeof='object'` 校验通过
  - stmt_09 更新 `raw_json` → stmt_10 删除 staging（**未并行** 9/10）
  - 验证：`id=27` **`raw_len=31394`**
- **exec_plan 批量续跑**：index **31 → 255**（共 224 步）
  - uid 34–62：INSERT + 分片填充 + raw_json 更新 + staging 清理
  - 末行 id=49（uid 62）剩余 10 步补跑完成，`raw_len=30267`
- **最终状态**：`result_items` **COUNT=47**，**good=47**（全部 `raw_len > 1000`），id 范围 3–49
- 新增脚本：`scripts/_mcp_prep_uid27_stmt.py`、`scripts/_pg_exec_sql_file.py`、`scripts/_pg_exec_plan_loop.py`

| 表 | 当前行数 | 目标 | 状态 |
|---|---:|---:|---|
| result_items | 47 | 47 | ✓ |
| price_snapshots | 338 | 338 | ✓ |
| seller_profiles | 6 | 6 | ✓ |

### chore(supabase): 暂停东京旧库并恢复 qwerty-learner

- 暂停 `goodfish`（`wkhatdhgohkpsqkytotz`，东京；数据已在新加坡）
- 恢复 `qwerty-learner`（`opagmkabncgryfhhpgzl`）
- 永久删除旧项目需在 Dashboard → Settings → General → Delete project

### chore(db): uid 31 修复完成 + exec_plan 续跑（25/47，uid 33 进行中）

- **uid 31 / id=26 修复完成**：顺序 MCP 执行 `mcp_chunks_uid26/stmt_03`–`stmt_08`（跳过 stmt_02，行已存在）
  - staging 重建：6000 → 12000 → 18000 → **19729**；`data::jsonb` 校验通过（`任务名称=机乐堂30w多口充电头`）
  - stmt_07 更新 `raw_json` → stmt_08 删除 staging（**未并行** 7/8）
  - 验证：`id=26` **`raw_len=19729`**（原 `{}` / raw_len=2）
- **exec_plan 进度**：index **17 → 26**（advance +9 跳过 uid 31 全部分片）→ 续跑 uid 33
  - uid 33：chunk 0–2（CREATE/DELETE/INSERT id=27）+ chunk 3（staging INSERT row 27，staging_len=6000）已完成
  - 当前 **index=31/255**（下一步 uid 33 chunk 4，`mcp_chunks_uid27/stmt_04.sql`）
- MCP COUNT：**25/47**；`id=27` `raw_len=2`（staging 填充中）
- 新增脚本：`scripts/_mcp_prep_repair_stmt.py`（按 stmt 编号准备 CallDynamicTool payload）

| 表 | 当前行数 | 目标 | 状态 |
|---|---:|---:|---|
| result_items | 25 | 47 | 进行中（exec_plan **31/255**） |
| price_snapshots | 338 | 338 | ✓ |
| seller_profiles | 6 | 6 | ✓ |

### chore(db): result_items MCP 导入续跑（24/47，uid 31 待修复 raw_json）

- **uid 30 完成**（INSERT id=25，分片 `mcp_chunks_uid25`）：exec_plan **index 11→17**（chunk 0–9 全部 MCP 成功）
- **uid 31 部分完成**（INSERT id=26 已入库，`raw_json` 仍为 `{}`）：step_012 **fetch failed** 后误执行 step_014 清空 staging → **须重跑 batch step_009–013**（`data/_mcp_batch/step_009.sql` … `step_013.sql`），**禁止在 step_013 前 DELETE staging**
- MCP COUNT：**24/47**；`id=26` `json_len=2`（待修复）
- 新增脚本：`scripts/_mcp_prep_current.py`、`scripts/_mcp_agent_exec_batch.py`、`scripts/_mcp_load_batch_step.py`、`scripts/_mcp_apply_batch_range.py`
- 限制不变：仅 `CallDynamicTool execute_sql`；HTTP/psycopg 直连不可用

| 表 | 当前行数 | 目标 | 状态 |
|---|---:|---:|---|
| result_items | 24 | 47 | 进行中（exec_plan **17/255**；uid 31 修复后 advance +9） |
| price_snapshots | 338 | 338 | ✓ |
| seller_profiles | 6 | 6 | ✓ |

### chore(db): result_items MCP 导入续跑（22/47，uid 30 进行中）

- **uid 27 完成**：chunk 3–10 全部 MCP 执行；`id=23` `raw_len=36467`，`task_name` 校验通过
- **uid 29 完成**（INSERT id=24，9595B 分片）：`raw_len=8008`；**须顺序执行** chunk 5→6（不可并行，否则 staging 被删导致 raw_json null）
- 队列：`next_uid=29`（done 含 27/28）；执行计划 `data/_mcp_exec_plan.json` **255 步**（243 chunk + 8 skip_delete + 4 execute），进度 **7/255**（uid 30 待续）
- 新增脚本：`scripts/_mcp_build_exec_plan.py`、`scripts/_mcp_exec_plan_step.py`、`scripts/_mcp_run_exec_plan.py`（HTTP 401，不可用）
- 限制不变：仅 `CallDynamicTool execute_sql` 可用

| 表 | 当前行数 | 目标 | 状态 |
|---|---:|---:|---|
| result_items | 22 | 47 | 进行中（exec_plan 7/255，uid 30+） |
| price_snapshots | 338 | 338 | ✓ |
| seller_profiles | 6 | 6 | ✓ |

### chore(db): uid 27 分片导入完成（21/47，续跑 uid 28+）

- 接续 [Retry uid 27 and finish import](0a4a7a9b-a238-4627-a06f-ad76c615e135)：通过 MCP 逐条执行 **chunk 3–10**（staging 写入 → 更新 `result_items.raw_json` → 清理 staging）
- MCP 验证：`id=23` **`raw_len=36467`**（有效 JSON object；本地组装预期 ~30467B，略大可能因并发重试，待全量导入后 spot-check）
- 队列 **uid 27 已标记完成**，`next_uid=28`
- 新增辅助脚本：`scripts/_validate_uid23_json.py`（离线校验分片 JSON 可解析性）
- 限制不变：Shell MCP 401；psycopg 直连密码失败；仅 `CallDynamicTool execute_sql` 可用

| 表 | 当前行数 | 目标 | 状态 |
|---|---:|---:|---|
| result_items | 21 | 47 | 进行中（uid 28–64 待续） |
| price_snapshots | 338 | 338 | ✓ |
| seller_profiles | 6 | 6 | ✓ |

### chore(db): uid 27 分片导入（21/47，进行中）

- uid **27**（INSERT id=23，32006B）改用 **分片 staging** 方案（`_mcp_json_staging` 表），避免 32KB 单条 MCP query 截断
- **part0 已完成**（MCP）：建 staging 表 + 插入 id=23 基础行（`raw_json='{}'`）
- MCP 验证：`id=23` 存在，`raw_len=2`，staging 暂空 → **待执行 chunk 3–10**（`data/mcp_chunks_uid23/`，最大单条 6065B）
- 新增脚本：`scripts/_mcp_split_large_insert.py`、`scripts/_mcp_run_chunks.py`
- 限制不变：Shell MCP 401；psycopg 直连密码失败；仅 `CallDynamicTool execute_sql` 可用

| 表 | 当前行数 | 目标 | 状态 |
|---|---:|---:|---|
| result_items | 21 | 47 | 进行中（id=23 占位，raw_json 未填充） |
| price_snapshots | 338 | 338 | ✓ |
| seller_profiles | 6 | 6 | ✓ |

### chore(db): result_items MCP 导入续跑（20/47，进行中）

- [Complete result_items MCP import](5f304aac-e506-4322-bc4d-4353872604e6) 本批完成：uid **25**（INSERT id=21，31386B）、uid **26**（INSERT id=22，19213B）→ `batch done`
- MCP COUNT 实测：**result_items=20**（目标 47）；`price_snapshots=338` ✓；`seller_profiles=6` ✓
- 队列：`next_uid=27`（done 29/65，remaining 38）；`batch_pending=true`（uid 27，32006B）
- uid 27：首次 MCP 因 **query 截断**（raw_json 仅 2408B）已 `DELETE id=23`；完整 payload 已写入 `data/.invoke_args.json`（32006B）**待重试 MCP**
- 已启动 [Retry uid 27 and finish import](0a4a7a9b-a238-4627-a06f-ad76c615e135) 全量重试 uid 27 并续跑至 uid 63/64
- 流程（未变）：`--check` → `CallDynamicTool execute_sql`（`json.load(.invoke_args.json)` 全量 query）→ `done`
- 限制：Shell MCP 401；psycopg 直连失败；大 SQL 用 `prepare 1`

| 表 | 当前行数 | 目标 | 状态 |
|---|---:|---:|---|
| result_items | 20 | 47 | 进行中 |
| price_snapshots | 338 | 338 | ✓ |
| seller_profiles | 6 | 6 | ✓ |

### chore(db): result_items MCP 导入续跑（17/47，进行中）— 已 superseded

- [Finish result_items MCP import](b32c80f3-0981-4f29-a1ee-a6a28e540d28) 续跑至 uid 22；MCP COUNT 实测 **17/47**
- 队列：`next_uid=23`（done 25/65）；uid 23 已 `prepare`（16433B）**待 MCP 执行**
- 错误/限制（未变）：Shell MCP 401；仅 `CallDynamicTool execute_sql` 可用；禁止截断 query

| 表 | 当前行数 | 目标 |
|---|---:|---:|
| result_items | 17 | 47 |
| price_snapshots | 338 | 338 |
| seller_profiles | 6 | 6 |

### chore(db): result_items MCP 导入续跑（14/47，进行中）— 已 superseded

- [Complete result_items MCP import](c70822d3-4e79-42ad-99f6-3bf688aa0985) 续跑：**14/47** `result_items`（id 3–16），`price_snapshots=338`，`seller_profiles=6` ✓
- 本批次完成：uid **18**（prepare 1 → MCP execute_sql 18373B → done，INSERT id=16）
- 队列：`next_uid=19`；uid 19 已 `prepare 1`（31290B）**待 MCP 执行**
- 错误/限制（未变）：
  - Shell MCP 桥接（`_mcp_call_from_invoke.py`）仍 **401**
  - 直连 PostgreSQL **密码认证失败**
  - 大 unit（>25KB）必须 `prepare 1`；禁止截断 query
- 待办：uid **19–62** INSERT + uid **63**（`__count__`）+ uid **64**（`__setval__`）；目标 `result_items=47`
- 已启动 [Finish result_items MCP import](b32c80f3-0981-4f29-a1ee-a6a28e540d28) 从 uid 19（已 prepare，31290B）续跑至完成

| 表 | 当前行数 | 目标 |
|---|---:|---:|
| result_items | 14 | 47 |
| price_snapshots | 338 | 338 |
| seller_profiles | 6 | 6 |

### chore(db): result_items MCP 导入续跑（13/47，进行中）— 已 superseded

- 上一阶段：**13/47**（id 3–15）；uid 13–15、17 已完成；uid 18 当时已 prepare 待执行

### chore(db): result_items MCP 导入续跑（9/47，进行中）— 已 superseded

- [Complete result_items MCP import](e2d50448-fd22-4542-97ac-6cfe48105f0d) 写入 **8/47** 行后暂停
- 修复队列缺口：uid 10 已入库但未标记 → 补标；uid 11（id=11）已通过 MCP 插入 → queue `next_uid=12`
- 已启动 [Finish result_items MCP import](b3e6b6ba-2fc0-4204-856d-33ec804d7269) 批量续跑（`prepare 3` → MCP → `done`）
- 工具链：`_mcp_batch_inserts.py`、`_mcp_import_skip_delete.py`（自动跳过 chunk 内 DELETE）
- **阻塞未变**：`.env` `DATABASE_URL` 密码无效；Shell MCP 401；仅 `CallDynamicTool execute_sql` 可用

### chore(db): result_items 专用 MCP 队列重建

- 从 `data/pg_migration/tables/chunks/result_items/*.sql` 重建 **65 unit**（`ri_XXXX.sql` + COUNT + setval）
- 旧 55-unit 队列（`import_05`~`import_33`）已废弃（会漏 chunk 001~004 且重复 price_snapshots）

### chore(db): Supabase MCP 顺序导入队列（已 superseded）

- 原 55-unit 队列（`import_05`~`import_33`）已被 result_items 专用队列取代

### chore(db): 迁移 Supabase 东京 → 新加坡（goodfish-sg）已完成

- 新建项目 **goodfish-sg**（`vcojlixcuqinanjlflgd`，`ap-southeast-1`）；免费配额满时暂停了 `qwerty-learner`
- 应用全部 migration；经 `postgres_fdw` 从东京库拉取大表，小表经 MCP 导入
- 新加坡库行数已与东京一致：tasks=2、result_items=47、price_snapshots=338、seller_subscriptions=1 等
- `.env` `DATABASE_URL` 已改为新加坡 pooler；`docs/database-supabase-integration.md` 已更新
- 新增脚本：`scripts/migrate_postgres_to_postgres.py`、`scripts/build_fdw_import_sql.py` 等
- **需你操作**：在 [Database Settings](https://supabase.com/dashboard/project/vcojlixcuqinanjlflgd/settings/database) **重置数据库密码**并更新 `.env`（新项目密码与东京不同）；若 `ECIRCUITBREAKER` 等几分钟再连

### fix(web-ui): TaskForm.vue watch 语法错误

- 移除 `seller_subscription` 任务类型后遗漏的 `}`，修复 Vite 编译 `Unexpected token`

## 2026-09-15

### fix(db): 连接超时 + bootstrap 进程内缓存，修复 API 偶发 500/挂起

- `db_connection` 增加 `connect_timeout=10`、TCP keepalive，并对 `OperationalError` 自动重连一次
- `bootstrap_storage` 启动成功后进程内跳过重复初始化；`ensure_schema` 在库内打标后跨进程也不再重复跑 DDL

### fix(scraper): 增强快照加载修复 CDN ERR_INVALID_ARGUMENT

- Chrome 扩展导出的 `state/*.json` 不再把 `Sec-Fetch-*` / `Referer` 注入为全局 `extra_http_headers`（跨域 CDN 会报 `net::ERR_INVALID_ARGUMENT`）
- 增强快照同时恢复 `storage.local` / `storage.session` 到 Playwright `storage_state.origins`，不再只传 cookies
- 新增 `tests/unit/test_scraper_snapshot.py`

### fix(seller-subscription): 订阅采集默认有头浏览器

- 无头模式无法加载用户主页 MTOP API（登录态正常也会 0 条）；订阅任务默认 `run_headless=false`
- `launch_task_browser` 支持 `task_config.run_headless` 覆盖全局 `RUN_HEADLESS`

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

## 2026-09-16

### chore(db): Supabase MCP 导入 result_items（进行中）

- **项目**: `vcojlixcuqinanjlflgd` (goodfish-sg)
- **队列**: `data/mcp_unit_queue.json`，65 units（chunk 001–016 + COUNT + setval）
- **策略**: 仅 uid=0 执行 `DELETE`；uid>0 的 DELETE unit 自动跳过；INSERT 通过 `CallDynamicTool execute_sql` 执行（Shell bridge 401）
- **查询加载**: 必须从 `data/.invoke_args.json` 经 `json.load` 完整读取，不可截断
- **辅助脚本**: `_mcp_batch_inserts.py`（批量 3 条）、`_mcp_import_skip_delete.py`、`_mcp_agent_execute_one.py`

**当前进度（会话末）**:

| 指标 | 值 |
|------|-----|
| `result_items` DB 行数 | **8 / 47** |
| 队列 `next_uid` | 10 |
| 已完成 uids | 0–5, 8, 6–9（batch） |
| 待执行 batch | uids 10✅, 11, 13（uid 12 DELETE 已跳过） |

**7 表 COUNT 验证（2026-09-16）**:

| 表 | 实际 | 目标 |
|----|------|------|
| result_items | 8 | 47 |
| price_snapshots | 338 | 338 ✅ |
| seller_profiles | 6 | 6 ✅ |
| app_metadata | 5 | — |
| tasks | 2 | — |
| seller_subscriptions | 1 | — |
| result_blacklist_rules | 1 | — |

**后续步骤**:

1. 执行 uids 11、13 MCP，然后 `python scripts/_mcp_batch_inserts.py done`
2. 循环 `prepare 3` → MCP → `done` 直至 `next_uid >= 65`
3. 执行 uid 63（COUNT）与 uid 64（setval）
4. 验证 `result_items = 47`

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
