# SQLite → MySQL 迁移计划

本文档描述将 `ai-goofish-monitor` 从 **SQLite（`data/app.sqlite3`）** 迁到 **MySQL 8.x** 的范围、阶段与验收标准。当前代码以同步 `sqlite3` + `asyncio.to_thread` 为主，表结构定义在 `src/infrastructure/persistence/sqlite_connection.py`。

---

## 1. 现状盘点

### 1.1 数据表（7 张逻辑表）

| 表名 | 用途 | 量级特征 |
|------|------|----------|
| `app_metadata` | 启动迁移标记、配置键值 | 极小 |
| `tasks` | 监控任务配置 | 小（通常 < 100 行） |
| `result_items` | 爬取结果（`raw_json` 大字段） | **大**，持续增长 |
| `price_snapshots` | 关键词行情快照 | 中～大 |
| `result_blacklist_rules` | 结果文件级黑名单 JSON | 小 |
| `collected_items` | 收录 + SKU JSON | 中 |

### 1.2 代码耦合点

| 模块 | 文件 | 说明 |
|------|------|------|
| Schema / 连接 | `sqlite_connection.py` | 建表、WAL、`sqlite_connection()` |
| 启动导入 | `sqlite_bootstrap.py` | 从 `config.json` / `jsonl/` 一次性导入 |
| 任务仓储 | `sqlite_task_repository.py` | 已实现 `TaskRepository` 接口 |
| 结果读写 | `result_storage_service.py` | **大量原生 SQL**（分页、黑名单、状态） |
| 行情 | `price_history_service.py` | `INSERT OR IGNORE` |
| 收录 | `collection_service.py` | JOIN `result_items` |
| 入口 | `app.py`, `dependencies.py`, `spider_v2.py` | 硬编码 `SqliteTaskRepository` |

### 1.3 SQLite 方言依赖（迁移时必须改写）

- `INSERT OR IGNORE` → MySQL `INSERT IGNORE` 或 `ON DUPLICATE KEY UPDATE`
- `INSERT OR REPLACE` → `REPLACE INTO` 或 `ON DUPLICATE KEY UPDATE`
- `INTEGER PRIMARY KEY AUTOINCREMENT` → `BIGINT AUTO_INCREMENT`
- `PRAGMA table_info` / 手写 `_migrate_*` → **Alembic** 或版本化 SQL 迁移
- 布尔字段存 `INTEGER 0/1` → MySQL `TINYINT(1)` 或 `BOOLEAN`
- 时间多为 **ISO 字符串** → 可保留 `VARCHAR` 或统一迁为 `DATETIME(3)`（建议二期再改类型）

### 1.4 非 DB 持久化（本次可不动）

- `state/` 登录态、`prompts/`、`images/`、`logs/`、`jsonl/` 历史文件  
- 迁移目标仅是 **在线主库**；文件仍放磁盘或对象存储。

---

## 2. 目标架构

### 2.1 配置

```env
# 驱动：sqlite | mysql（过渡期双支持，最终默认 mysql）
DATABASE_DRIVER=mysql

# SQLite（兼容）
APP_DATABASE_FILE=data/app.sqlite3

# MySQL
DATABASE_URL=mysql+asyncmy://user:pass@host:3306/goofish?charset=utf8mb4
# 或分拆：
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=goofish
MYSQL_PASSWORD=***
MYSQL_DATABASE=goofish
```

### 2.2 分层（与现有 AGENTS 一致）

```
API / spider_v2
    → Service（TaskService, ResultStorage, Collection, PriceHistory）
    → Repository 接口（Task / ResultItem / Collection / PriceSnapshot）
    → 实现：Sqlite*Repository（过渡期） / Mysql*Repository
    → 连接池 + 迁移工具（Alembic）
```

**原则**：业务层不再直接 `import sqlite_connection`；SQL 集中在 `infrastructure/persistence/mysql/`（或 SQLAlchemy models）。

### 2.3 技术选型建议

| 选项 | 优点 | 缺点 |
|------|------|------|
| **SQLAlchemy 2.0 + Alembic**（推荐） | 迁移可版本化、方言抽象好 | 需把散落的 raw SQL 逐步收口 |
| **aiomysql/asyncmy + 手写 SQL** | 与现状接近、改动面可控 | 长期维护成本高 |

推荐：**SQLAlchemy Core + Alembic** 管 schema；热点查询（结果分页）可保留显式 SQL，但通过 `session.execute(text(...))` 统一入口。

### 2.4 MySQL 物理设计要点

- 字符集：**utf8mb4**，排序规则 `utf8mb4_unicode_ci`
- `result_items.raw_json`：`LONGTEXT`（单条可能数百 KB）
- `collected_items.sku_json`：`JSON` 类型（MySQL 8）或 `LONGTEXT`
- 唯一约束保持：`(result_filename, link_unique_key)`、`collected_items.result_item_id`
- 外键：`collected_items.result_item_id` → `result_items.id` **ON DELETE CASCADE**
- 索引：沿用现有组合索引；大表考虑按 `crawl_time` 分区（**可选，二期**）
- `tasks.id`：改为 `AUTO_INCREMENT`；导入时保留原 id 需 `SET FOREIGN_KEY_CHECKS=0` 批量导入

---

## 3. 分阶段实施计划

### 阶段 A：准备与基线（不切换生产）

1. 新增 `docs/database-mysql-migration-plan.md`（本文）与 `.env.example` MySQL 变量。
2. 引入依赖：`sqlalchemy[asyncio]`、`alembic`、`asyncmy`（或 `aiomysql`）。
3. 用 Alembic **从当前 SQLite schema 导出** MySQL 初版 DDL（`alembic revision --autogenerate` 对照手写修正）。
4. Docker Compose 增加 `mysql:8` 服务 + 健康检查；应用 `depends_on: mysql:healthy`。
5. 单元/集成测试：pytest 用 **Testcontainers MySQL** 或固定 CI 服务（与 SQLite `tmp_path` 并行）。

**验收**：空库 `alembic upgrade head` 成功；应用能以 `DATABASE_DRIVER=sqlite` 仍全部通过现有测试。

---

### 阶段 B：仓储抽象与 MySQL 实现（双驱动）

1. 定义仓储接口（扩展现有 `TaskRepository`）：
   - `ResultItemRepository`（query/save/delete/status/blacklist）
   - `PriceSnapshotRepository`
   - `CollectionRepository`
2. 将 `result_storage_service.py` / `collection_service.py` / `price_history_service.py` 中的 SQL **下沉**到仓储实现；Service 只调接口。
3. 实现 `MysqlTaskRepository` 等，与 `Sqlite*` 行为对齐（含 `INSERT IGNORE` 语义）。
4. `dependencies.py` / `app.py` / `spider_v2.py` 通过工厂选择实现：

   ```python
   def get_task_repository() -> TaskRepository:
       if settings.database_driver == "mysql":
           return MysqlTaskRepository(...)
       return SqliteTaskRepository(...)
   ```

5. `sqlite_bootstrap` 逻辑：MySQL 模式下仅当表为空时可选从 legacy 文件导入（与现逻辑一致）。

**验收**：`DATABASE_DRIVER=mysql` 下跑通：创建任务、跑 spider（或 mock）、写入 `result_items`、结果 API 分页、收录 + SKU 字段读写。

---

### 阶段 C：历史数据迁移（一次性工具）

1. CLI：`python -m scripts.migrate_sqlite_to_mysql`  
   - 读 `APP_DATABASE_FILE`  
   - 按表顺序写入 MySQL：`app_metadata` → `tasks` → `result_items` → `price_snapshots` → `result_blacklist_rules` → `collected_items`  
   - 批量插入（如 500～1000 行/批），`result_items` 单独计时  
   - 迁移后校验：各表 `COUNT(*)`、抽样 `id`/`link_unique_key`、checksum 可选  
2. 支持 `--dry-run`、`--tables tasks,result_items`。
3. 大库注意：停写窗口或 **只读模式** 下迁移；或先迁历史 + 增量 binlog（一般本项目体量 **停写 5～15 分钟** 足够）。

**验收**：迁移后 Web 结果列表、收录详情与 SQLite 源库抽样一致（至少 20 条 diff 对比 `raw_json` MD5）。

---

### 阶段 D：灰度与切换

1. **双写（可选，数据量大时）**：短周期内 `DATABASE_DRIVER=dual`，写 SQLite + MySQL，读仍 SQLite；对账脚本比对行数。  
   - 体量小可 **跳过双写**，直接停服务 → 迁移 → 改配置 → 启动。
2. 切换步骤（推荐）：
   1. 停止调度与爬虫进程  
   2. 备份 `data/app.sqlite3`  
   3. 执行迁移 CLI  
   4. 设置 `DATABASE_DRIVER=mysql`，重启 API  
   5.  smoke：登录、任务列表、结果页、收录拉 SKU  
3. 回滚：保留 SQLite 备份；配置改回 `sqlite` 并重启（MySQL 侧数据可丢弃或保留对账）。

**验收**：生产/云端连续运行 24h 无连接池耗尽、无死锁；慢查询日志无全表扫。

---

### 阶段 E：收尾

1. 默认驱动改为 `mysql`；文档更新 README / Docker / user-guide。
2. SQLite 实现标记 `@deprecated`，保留 1～2 个版本供本地轻量使用（可选）。
3. 删除散落的 `sqlite_connection` 直接引用（grep 为零）。
4. 监控：连接数、慢查询、`result_items` 表大小；必要时归档冷数据。

---

## 4. MySQL DDL 草案（与 SQLite 对齐）

详见迁移仓库中的 Alembic `versions/001_initial_mysql.py`（实施阶段 A 产出）。核心映射：

- `tasks.enabled` → `TINYINT(1) NOT NULL`
- `result_items.id` → `BIGINT UNSIGNED AUTO_INCREMENT`
- `UNIQUE KEY uq_result_link (result_filename, link_unique_key)`
- `KEY idx_results_filename_crawl (result_filename, crawl_time DESC)`  
  （MySQL 8 降序索引支持；或与查询一致用 `(result_filename, crawl_time)`）

---

## 5. 测试策略

| 层级 | 内容 |
|------|------|
| 单元 | 仓储 CRUD、唯一键冲突、`INSERT IGNORE` 行为 |
| 集成 | `test_api_tasks` / `test_api_results` / dashboard 在 MySQL fixture 上跑 |
| 迁移 | 固定小型 `tests/fixtures/app.sqlite3` → 临时 MySQL → 行数与 JSON 一致 |
| 性能 | `result_items` 1万行分页 P95 < 500ms（调索引与 `LIMIT`） |

---

## 6. 风险与对策

| 风险 | 对策 |
|------|------|
| `raw_json` 过大导致包体/内存问题 | 分页只 SELECT 列表列；详情再取 `raw_json`（二期列拆分） |
| 连接池在爬虫子进程与 API 间争用 | 爬虫继续写库经 API 或独立池配置；子进程只读任务可缓存 |
| SQLite 与 MySQL 布尔/时间差异 | 仓储层统一转换；不改前端契约 |
| 迁移中途失败 | 事务按表提交；记录 checkpoint；可 TRUNCATE 重跑单表 |
| 云端无 MySQL | Compose 内嵌或托管 RDS；Secrets 注入 `DATABASE_URL` |

---

## 7. 建议执行顺序（ checklist ）

- [ ] A1 Alembic 初始化 + MySQL DDL  
- [ ] A2 Docker MySQL + `.env.example`  
- [ ] B1 ResultItem / Collection / PriceSnapshot 仓储接口  
- [ ] B2 MySQL 仓储实现 + 工厂注入  
- [ ] B3 全量 pytest（sqlite + mysql 矩阵）  
- [ ] C1 `migrate_sqlite_to_mysql` CLI  
- [ ] D1 预发迁移演练 + 回滚演练  
- [ ] D2 生产切换  
- [ ] E1 文档与默认驱动  

---

## 8. 与当前功能的关系

- **收录 / SKU**：依赖 `result_items.id` 外键；迁移时必须 **先迁 result_items 再迁 collected_items**，并保持 id 一致（迁移脚本用 `INSERT` 保留主键）。
- **黑名单 / 隐藏状态**：`result_items.status` 已在 SQLite；MySQL 初版 DDL 应 **直接包含** `status`，避免再靠 PRAGMA 补丁。

---

## 9. 需要你方确认的产品决策

1. MySQL 部署形态：**Docker 同机** / **云 RDS** / **自建**？  
2. 是否接受迁移窗口 **短暂停写**（推荐小团队），还是必须双写？  
3. `result_items` 是否要做 **冷热分离**（例如 90 天前归档表）？  
4. 爬虫子进程是否继续 **直连数据库**，还是改为 **只调 HTTP API 写结果**（利于以后多实例）？

确认后可按阶段 A 开 PR，单 PR 建议只做到「MySQL 空库可启动 + 任务 CRUD」，避免一次改完全部 SQL。
