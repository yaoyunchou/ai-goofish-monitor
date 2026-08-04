# 变更日志

## 2026-08-04

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
- 保留 `.env.20260803` 作为测试环境配置备份（后续由你自行改密码/连接串）
- 新增 `.env.20260804`：自当前 `/workspace/.env` 复制的配置快照

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
