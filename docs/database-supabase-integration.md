# Supabase（PostgreSQL）接入指南

项目：**wkhatdhgohkpsqkytotz**  
API URL：`https://wkhatdhgohkpsqkytotz.supabase.co`  
Dashboard：[Project Settings](https://supabase.com/dashboard/project/wkhatdhgohkpsqkytotz/settings/general)

> **重要**：当前应用代码仍默认 **SQLite**（`data/app.sqlite3`）。本文说明如何在 Supabase 建库、如何配置环境变量，以及切换到 Postgres 前需要完成的代码改造（与 [database-mysql-migration-plan.md](./database-mysql-migration-plan.md) 同路线，引擎改为 Postgres）。

---

## 1. 在 Supabase 上建表（你现在就能做）

任选其一：

### 方式 A：SQL Editor（最快）

1. 打开 [SQL Editor](https://supabase.com/dashboard/project/wkhatdhgohkpsqkytotz/sql/new)
2. 粘贴并执行仓库内：  
   `supabase/migrations/20260803120000_initial_goofish_schema.sql`
3. 在 **Table Editor** 中确认出现：`tasks`、`result_items`、`price_snapshots`、`collected_items` 等

### 方式 B：Supabase CLI（推荐长期维护）

```bash
# 安装 CLI 后
supabase login
supabase link --project-ref wkhatdhgohkpsqkytotz
supabase db push
```

迁移前请用 `supabase migration new <name>` 创建新文件（勿手写随机文件名），见官方 CLI 文档。

---

## 2. 连接串怎么选（给 Python 后端用）

在 Dashboard → **Project Settings → Database → Connection string**：

| 模式 | 适用场景 | 端口 |
|------|----------|------|
| **Direct connection** | 迁移 DDL、长连接、爬虫 + API 同机 | `5432`，主机 `db.wkhatdhgohkpsqkytotz.supabase.co` |
| **Session pooler** | 多进程/连接较多时的池化 | 通常 `5432`，用户 `postgres.wkhatdhgohkpsqkytotz` |
| **Transaction pooler** | Serverless 短请求 | `6543`（本项目 **不推荐** 作为首选） |

**本仓库（FastAPI + 爬虫子进程）建议**：优先 **Direct** 或 **Session pooler**。

密码使用 **Database password**（创建项目时设置，可在 Database Settings 里重置），**不是** `anon` / `service_role` JWT。

### `.env` 配置模板（勿提交密码）

```env
# 目标：sqlite | postgres（postgres 实现待代码合并后生效）
DATABASE_DRIVER=sqlite

# --- Supabase Postgres（DATABASE_DRIVER=postgres 时使用）---
# SQLAlchemy + asyncpg 推荐写法（密码含特殊字符请 URL 编码）
DATABASE_URL=postgresql+asyncpg://postgres:[YOUR-DB-PASSWORD]@db.wkhatdhgohkpsqkytotz.supabase.co:5432/postgres

# 若使用 Session pooler，将主机/用户换为控制台给出的 Pooler 串，例如：
# DATABASE_URL=postgresql+asyncpg://postgres.wkhatdhgohkpsqkytotz:[PASSWORD]@aws-0-[region].pooler.supabase.com:5432/postgres

# 仅当你通过 Supabase JS/REST 调 Storage/Auth 时才需要（本项目的 Web 仍走 FastAPI 时可不配）
# SUPABASE_URL=https://wkhatdhgohkpsqkytotz.supabase.co
# SUPABASE_SERVICE_ROLE_KEY=   # 仅后端服务器，禁止写入前端或提交 Git
```

本地仍用 SQLite 时保留：

```env
DATABASE_DRIVER=sqlite
APP_DATABASE_FILE=data/app.sqlite3
```

---

## 3. 和 Supabase「API Keys」的关系

| 密钥 | 用途 | 本项目 |
|------|------|--------|
| **Database 连接串 + DB 密码** | `psycopg` / `asyncpg` 直连 SQL | **承接 tasks / results 等主数据（目标方案）** |
| `anon` / publishable | 浏览器端 Supabase Client | **不必**用于闲鱼监控业务表 |
| `service_role` | 服务端绕过 RLS 的 REST | 仅在你主动用 Supabase API 时需要；**勿暴露给 Vue 前端** |

当前架构：**Vue → FastAPI → PostgreSQL**，不强制接入 Supabase Auth。

---

## 4. RLS 说明（已写入初始 migration）

业务表已 `ENABLE ROW LEVEL SECURITY`，且**未**对 `anon` / `authenticated` 添加开放策略 → 通过 Supabase Data API 默认无法读业务表。  
后端使用 **Database 连接串**（`postgres` 数据库用户）读写不受 PostgREST 策略影响。

若以后要开放移动端直连 Supabase，需单独设计 RLS，且**不要用 `user_metadata` 做授权**（见 Supabase 安全文档）。

---

## 5. 应用侧还要改什么（才能真用上 Supabase）

代码现状：全部走 `sqlite_connection` + `SqliteTaskRepository`。

切换步骤（与 MySQL 计划相同，方言改为 Postgres）：

1. `DATABASE_DRIVER=postgres` + `DATABASE_URL`
2. 实现 Postgres 仓储（或 SQLAlchemy + Alembic）
3. `INSERT OR IGNORE` → `ON CONFLICT DO NOTHING` 等
4. 可选 CLI：`sqlite → postgres` 数据迁移（保留 `result_items.id` 以兼容 `collected_items` 外键）
5. 集成测试在 Supabase **分支库** 或本地 `supabase start` 上跑

- 代码已支持 `DATABASE_DRIVER=postgres` + `DATABASE_URL`（`psycopg` 直连）；切换后重启 API/爬虫

---

## 6. 连通性自检（建表后）

在已安装 `psycopg` 或 `asyncpg` 的机器上（密码勿泄露）：

```bash
# 使用控制台复制的 URI，或：
psql "postgresql://postgres:[PASSWORD]@db.wkhatdhgohkpsqkytotz.supabase.co:5432/postgres" -c "SELECT COUNT(*) FROM tasks;"
```

或在 SQL Editor：

```sql
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public' AND table_name IN ('tasks', 'result_items', 'collected_items');
```

---

## 7. 你需要在 Cursor 里做的（可选）

若希望 Agent 通过 MCP 直接查库、跑 advisors：

1. 配置 [Supabase MCP](https://supabase.com/docs/guides/getting-started/mcp) 并完成 OAuth
2. 关联 project `wkhatdhgohkpsqkytotz`

---

## 8. 检查清单

- [ ] SQL Editor 已执行 `20260803120000_initial_goofish_schema.sql`
- [ ] `.env` 已配置 `DATABASE_URL`（仅本机，不提交 Git）
- [ ] 已确认 IPv4：Supabase 直连需网络能访问 `db.*.supabase.co`（企业网需放行或使用 pooler）
- [ ] 代码合并 Postgres 驱动后，将 `DATABASE_DRIVER=postgres` 并重启 API / 爬虫
- [ ] 从 SQLite 迁移数据（若有历史 `app.sqlite3`）

如需下一步在仓库内实现 **Postgres 仓储 + 开关**，可指定优先模块（仅 tasks / 含 result_items）。
