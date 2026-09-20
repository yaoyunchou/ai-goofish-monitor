# 本地 PostgreSQL ↔ 线上 Supabase 双向数据同步

本文描述 **ai-goofish-monitor** 在「本机 Docker Postgres」与「线上 Supabase（goodfish / `wkhatdhgohkpsqkytotz`）」之间实现**双向同步**的目标、约束、表级策略与分阶段落地计划。  
当前仓库**仅实现单向拉取**（线上 → 本地）；双向能力需按本文后续阶段开发。

相关文档：

- [database-supabase-integration.md](./database-supabase-integration.md) — 连接串、建表、自检
- 迁移 SQL：`supabase/migrations/20260803120000_initial_goofish_schema.sql`

---

## 1. 术语与拓扑

| 名称 | 环境变量 | 典型用途 |
|------|-----------|----------|
| **本地库** | `DATABASE_URL` | 本机开发、`docker-compose.dev.yml` 中的 Postgres |
| **线上库** | `REMOTE_DATABASE_URL` | Supabase Session pooler，生产/共享数据 |

```
┌─────────────────┐         双向同步（目标）         ┌─────────────────┐
│  本地 Postgres   │ ◄──────────────────────────► │ Supabase Postgres │
│  127.0.0.1:5432  │   pull / push / merge        │  Tokyo pooler     │
└────────┬────────┘                                └────────┬────────┘
         │                                                  │
         └────────────── FastAPI / 爬虫 / Web UI ───────────┘
              （同一时刻只应有一个「主写入」环境，见 §4）
```

**原则**：两端 schema 必须一致（同一套 migration）；同步的是**业务表数据**，不包含 `state.json`、图片文件、`jsonl/` 等文件资产（除非另立「对象存储同步」方案）。

**闲鱼账号 / 登录态 Cookie** 在 `state/*.json`，**不在数据库**。详见 [sync-runtime-files.md](./sync-runtime-files.md)。

---

## 2. 同步范围（6 张业务表）

与 `scripts/sync_postgres_remote_to_local.py` 中 `TABLE_ORDER` 一致，外键依赖顺序如下：

| 顺序 | 表名 | 主键 / 业务唯一键 | 写入特征 | 双向建议 |
|------|------|-------------------|----------|----------|
| 1 | `app_metadata` | `key` | 启动 bootstrap 标记 | **双向**，量小 |
| 2 | `tasks` | `id`（IDENTITY） | Web UI 改配置 | **双向**，冲突敏感 |
| 3 | `result_items` | `id`；`UNIQUE(result_filename, link_unique_key)` | 爬虫追加 | **以追加为主**；同 key 合并 |
| 4 | `price_snapshots` | `id`；`UNIQUE(keyword_slug, run_id, item_id)` | 爬虫追加 | **以追加为主** |
| 5 | `result_blacklist_rules` | `result_filename` | Web UI 改规则 | **双向**，按 `updated_at` |
| 6 | `collected_items` | `id`；`UNIQUE(result_item_id)` → `result_items` | 收藏/SKU | **双向**，依赖 `result_items` 先齐 |

`collected_items.result_item_id` 引用 `result_items.id`：**跨库同步时必须先保证 `result_items` 在两端 id 一致**，或改为按业务键（`result_filename` + `link_unique_key`）解析后再插入。

---

## 3. 现状（已实现）

| 能力 | 脚本 | 方向 | 行为 |
|------|------|------|------|
| 全量拉取 | `python -m scripts.sync_postgres_remote_to_local` | 线上 → 本地 | `TRUNCATE` 本地 6 表后全量插入（保留远程 `id`） |
| 快照拉取 | `scripts/pull_supabase_to_snapshot.py` | 线上 → 文件 | 写入 `data/db_sync_snapshot/*.json` |
| 快照导入 | `scripts/import_db_sync_snapshot.py` | 文件 → 本地 | 同上，全量覆盖本地 |
| 单表导入 | `scripts/import_table_snapshot.py` | 文件 → 本地 | 只 `DELETE` + 插入指定表 |
| MCP 辅助 | `decode_mcp_b64_export.py`、`mcp_extract_rows.py` | 线上 → 文件 | 无 `REMOTE_DATABASE_URL` 时的应急导出 |

配置示例（`.env`）：

```env
DATABASE_URL=postgresql+asyncpg://postgres:goofish@127.0.0.1:5432/goofish
REMOTE_DATABASE_URL=postgresql+asyncpg://postgres.wkhatdhgohkpsqkytotz:[PASSWORD]@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres
```

**限制**：现有脚本**不会**把本地变更推送到线上，也**不会**合并冲突；本地全量导入会**清空**本地数据。

---

## 4. 推荐运行模式（避免双写混乱）

在双向同步未完全自动化前，建议明确「主库」：

| 模式 | 主写入 | 本地角色 | 典型操作 |
|------|--------|----------|----------|
| **生产主** | 线上 Supabase | 只读副本 / 调试 | 定期 `sync_postgres_remote_to_local` |
| **本地主** | 本地 Postgres | 开发改任务、试跑爬虫 | 开发结束后 **push 到线上**（待实现） |
| **分表主** | 按表划分 | 例如任务只改本地、结果只在线上产生 | 按表方向同步（待实现） |

**不要**同时在本地和线上用 Web UI / 爬虫写同一批 `tasks`，否则会出现 id 相同、内容不同的冲突。

---

## 5. 双向同步目标行为（产品定义）

### 5.1 三种操作

1. **Pull（拉）**：`REMOTE` → `LOCAL` — 与现有一致，可选「增量」替代全量 TRUNCATE。  
2. **Push（推）**：`LOCAL` → `REMOTE` — 把本地变更上传（待实现）。  
3. **Sync（合并）**：按行比较，双向补缺与更新（待实现，推荐最终形态）。

建议 CLI 形态（规划）：

```bash
python -m scripts.sync_postgres_bidirectional pull
python -m scripts.sync_postgres_bidirectional push
python -m scripts.sync_postgres_bidirectional sync    # 默认：合并
python -m scripts.sync_postgres_bidirectional sync --dry-run
python -m scripts.sync_postgres_bidirectional sync --tables tasks,result_blacklist_rules
```

### 5.2 行级相等与变更检测

当前表**缺少统一的 `updated_at TIMESTAMPTZ` / `row_version`**，仅部分字段为文本时间（如 `result_blacklist_rules.updated_at`、`result_items.crawl_time`）。

**阶段 A（无 schema 变更）**：  
- 用 **主键 + 全行内容哈希**（或 JSON 规范化后 SHA256）判断「是否相同」。  
- 缺点：无法识别删除；大表（`result_items`）全表扫描成本高。

**阶段 B（推荐，需 migration）**：为可双向表增加：

```sql
-- 示例：后续 migration 中增加
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
-- 应用层 UPDATE 时刷新 updated_at；软删除写 deleted_at
```

并新增 **同步元数据表**（本地、线上各一份，结构相同）：

```sql
CREATE TABLE IF NOT EXISTS sync_state (
    table_name TEXT PRIMARY KEY,
    last_pull_at TIMESTAMPTZ,
    last_push_at TIMESTAMPTZ,
    last_remote_max_updated_at TIMESTAMPTZ,
    last_local_max_updated_at TIMESTAMPTZ
);
```

增量同步：`WHERE updated_at > :watermark AND deleted_at IS NULL`。

### 5.3 冲突策略（按表）

当同一主键（或业务唯一键）在两端都被修改且内容不一致时：

| 表 | 建议策略 | 说明 |
|----|----------|------|
| `app_metadata` | **LWW**（Last Write Wins） | 比较 `updated_at` 或哈希时间戳；bootstrap 键以较新为准 |
| `tasks` | **LWW** 或 **主库优先** | 任务配置冲突应提示用户；默认 `REMOTE` 优先更安全 |
| `result_items` | **唯一键合并** | `(result_filename, link_unique_key)` 已存在则跳过或按 `crawl_time` 更新较新 |
| `price_snapshots` | **唯一键追加** | `(keyword_slug, run_id, item_id)` 冲突则保留一条（通常内容相同） |
| `result_blacklist_rules` | **LWW** | 已有 `updated_at` 文本，需规范为可比较时间 |
| `collected_items` | **LWW** + 外键检查 | 先同步 `result_items`；`result_item_id` 在目标库不存在则跳过并记日志 |

全局可选参数：`--prefer local|remote`（冲突时偏向哪一端）。

### 5.4 删除同步

- **硬删除**：一端 `DELETE` 后，另一端仍保留 → 数据分叉。  
- **推荐**：阶段 B 引入 `deleted_at` 软删除，同步时传播删除标记。  
- **保守策略（阶段 A）**：不同步删除，仅 **INSERT + UPDATE**；周期性全量 pull 校正（会覆盖本地）。

---

## 6. 同步顺序与事务

与单向脚本相同，**必须按依赖顺序**写入：

```
app_metadata → tasks → result_items → price_snapshots → result_blacklist_rules → collected_items
```

实现建议：

- 每表一个事务；失败则中止并输出已提交表清单。  
- `INSERT ... ON CONFLICT ... DO UPDATE`（Upsert）按表选择冲突目标（主键或 UNIQUE）。  
- 保留 `id` 时使用 `INSERT ... OVERRIDING SYSTEM VALUE`（与现 `_insert_batch` 一致）。  
- Push 到线上前：`python -m scripts.verify_database` + `--dry-run` 预览行数差异。

---

## 7. 安全与运维

1. **勿提交** `.env` 中的 `REMOTE_DATABASE_URL` 密码。  
2. **生产 push 前**：Supabase Dashboard 手动备份或使用 `pg_dump`（仅业务表）。  
3. **dry-run**：任何 push/sync 必须支持只统计「将插入/更新/跳过/冲突」而不写库。  
4. **连接**：两端均使用 **Session pooler**（IPv4 友好）；本地用 `127.0.0.1`。  
5. **RLS**：业务通过 `postgres` 角色直连，不受 RLS 影响；勿用 anon key 做同步。  
6. **大表**：`result_items` / `price_snapshots` 未来可做「按 `result_filename` / `keyword_slug` 分片同步」。

---

## 8. 分阶段实施计划

### 阶段 0 — 立即可用（已完成）

- [x] 线上 → 本地全量：`sync_postgres_remote_to_local`  
- [x] 快照管道 + MCP 应急导出  
- [x] `verify_database` 校验

### 阶段 1 — 单向推送（本地 → 线上）

- [ ] 新脚本 `sync_postgres_local_to_remote.py`（或 `bidirectional push`）  
- [ ] 复用 `_adapt_row` / `_insert_batch`，目标库 Upsert，**禁止**默认 TRUNCATE 线上  
- [ ] 支持 `--tables`、`--dry-run`  
- [ ] 文档与 `.env.example` 补充「本地主」工作流

### 阶段 2 — 增量与合并（双向 sync）

- [ ] Migration：`updated_at` / 可选 `deleted_at` / `sync_state`  
- [ ] `sync_postgres_bidirectional sync`：按 watermark 双向拉齐  
- [ ] 冲突日志表或控制台报告：`sync_conflicts.jsonl`  
- [ ] 单元测试：伪造两端数据，覆盖 Upsert、LWW、唯一键冲突

### 阶段 3 — 体验与自动化（可选）

- [ ] Web UI「同步」页：触发 pull/push、展示 diff 统计  
- [ ] 定时任务（仅 pull）或 CI 部署前 push 任务配置  
- [ ] 与 `config.json` 双写问题收口（任务以 DB 为准）

---

## 9. 日常操作速查（当前 + 规划）

| 目的 | 命令（当前） | 命令（规划） |
|------|----------------|----------------|
| 用线上覆盖本地 | `python -m scripts.sync_postgres_remote_to_local` | 同左，或 `... bidirectional pull --full` |
| 把本地任务推到线上 | — | `python -m scripts.sync_postgres_bidirectional push --tables tasks` |
| 双向合并 | — | `python -m scripts.sync_postgres_bidirectional sync --prefer remote` |
| 检查两端是否一致 | 本地 `verify_database` + 线上 SQL `COUNT(*)` | `... bidirectional diff` |
| 无密码应急拉取 | MCP + `decode_mcp_b64_export.py` + `import_table_snapshot.py` | 仅作备用 |

---

## 10. 实现时注意点（给开发）

1. **时间字段**：库内多为 `TEXT` 时间（如 `crawl_time`），合并前需统一解析为 UTC 再比较。  
2. **JSONB**：同步前后必须走 `_adapt_row`，避免 Python `list` 直接绑进 `::jsonb`。  
3. **IDENTITY / 序列**：每表写入后 `setval(pg_get_serial_sequence(...), max(id))`（现有 `_reset_sequences`）。  
4. **`is_running`**：任务运行态不应跨环境同步，或 sync 时强制置 `false`（避免线上显示本地僵尸状态）。  
5. **外键**：`collected_items` push 前校验 `result_item_id` 在目标库存在。  
6. **测试**：`pytest tests/.../test_sync_*.py`（阶段 2 起）用 Docker 起第二个 Postgres 实例模拟 REMOTE。

---

## 11. 检查清单（上线双向前）

- [ ] 本地与线上均已执行同一版本 migration  
- [ ] `.env` 同时配置 `DATABASE_URL` 与 `REMOTE_DATABASE_URL`  
- [ ] 已选定主库模式（§4）并告知团队  
- [ ] 已对线上做备份  
- [ ] 已用 `--dry-run` 看过 push/sync 统计  
- [ ] `python -m scripts.verify_database` 在本地通过  
- [ ] 两端 `COUNT(*)` 与抽样主键对比无意外差异  

---

## 12. 变更记录

| 日期 | 说明 |
|------|------|
| 2026-08-05 | 初版：双向同步目标、表策略、冲突与分阶段计划；当前仅单向拉取 |
