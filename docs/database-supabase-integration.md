# Supabase（PostgreSQL）接入指南

项目：**wkhatdhgohkpsqkytotz**  
API URL：`https://wkhatdhgohkpsqkytotz.supabase.co`  
Dashboard：[Project Settings](https://supabase.com/dashboard/project/wkhatdhgohkpsqkytotz/settings/general)

> 应用已全面切换到 **Postgres**，SQLite 已移除。本文说明如何在 Supabase 建库、如何配置连接串、以及连通性自检。

---

## 1. 在 Supabase 上建表（首次部署必做）

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

后续迁移请用 `supabase migration new <name>` 创建新文件（勿手写随机文件名），见官方 CLI 文档。

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
# --- Supabase Postgres（必填）---
# SQLAlchemy + asyncpg 推荐写法（密码含特殊字符请 URL 编码）
DATABASE_URL=postgresql+asyncpg://postgres:[YOUR-DB-PASSWORD]@db.wkhatdhgohkpsqkytotz.supabase.co:5432/postgres

# 若使用 Session pooler，将主机/用户换为控制台给出的 Pooler 串，例如：
# DATABASE_URL=postgresql+asyncpg://postgres.wkhatdhgohkpsqkytotz:[PASSWORD]@aws-0-[region].pooler.supabase.com:5432/postgres

# 仅当你通过 Supabase JS/REST 调 Storage/Auth 时才需要（本项目的 Web 仍走 FastAPI 时可不配）
# SUPABASE_URL=https://wkhatdhgohkpsqkytotz.supabase.co
# SUPABASE_SERVICE_ROLE_KEY=   # 仅后端服务器，禁止写入前端或提交 Git
```

> 直连在某些网络环境仅解析 IPv6，若不可达请改用 Session pooler 连接串，或在 Supabase 开启 IPv4 附加项。

---

## 3. 和 Supabase「API Keys」的关系

| 密钥 | 用途 | 本项目 |
|------|------|--------|
| **Database 连接串 + DB 密码** | `psycopg` / `asyncpg` 直连 SQL | **承接 tasks / results 等主数据** |
| `anon` / publishable | 浏览器端 Supabase Client | **不必**用于闲鱼监控业务表 |
| `service_role` | 服务端绕过 RLS 的 REST | 仅在你主动用 Supabase API 时需要；**勿暴露给 Vue 前端** |

当前架构：**Vue → FastAPI → PostgreSQL**，不强制接入 Supabase Auth。

---

## 4. RLS 说明（已写入初始 migration）

业务表已 `ENABLE ROW LEVEL SECURITY`，且**未**对 `anon` / `authenticated` 添加开放策略 → 通过 Supabase Data API 默认无法读业务表。  
后端使用 **Database 连接串**（`postgres` 数据库用户）读写不受 PostgREST 策略影响。

若以后要开放移动端直连 Supabase，需单独设计 RLS，且**不要用 `user_metadata` 做授权**（见 Supabase 安全文档）。

---

## 5. 历史数据导入（可选）

应用首次启动时会自动从遗留的 `config.json` / `jsonl/` / `price_history/` 一次性导入历史数据（仅当对应表为空时）。导入进度记录在 `app_metadata` 表的 `bootstrap:*` 键中。

如需从旧的本地 `data/app.sqlite3` 搬迁历史数据到 Postgres，目前需手动导出导入（保留 `result_items.id` 以兼容 `collected_items` 外键）。

---

## 6. 连通性自检（建表后）

仓库自带自检脚本：

```bash
pip install -r requirements.txt
python3 -m scripts.verify_database
```

脚本会检查核心表行数并对 `app_metadata` 做读写探针（不打印密码）。输出中会标注 `DATABASE_*` 来自 `env_file` 还是 `process_env`（如 Cursor Secrets）。

### 配置优先级（与 Web「系统状态」一致）

| 顺序 | 来源 | 说明 |
|------|------|------|
| 1 | 仓库根目录 **`.env`** | `env_manager` / 数据库连接 / `verify_database` 均**优先**读文件 |
| 2 | **进程环境变量** | 仅当 `.env` 中**没有**该键时生效（如 Cursor Cloud **Secrets**） |

因此：本机改好 `.env` 后，在 Cloud Agent 若仍连错库，请检查 Secrets 是否仍注入旧的 `DATABASE_URL`；或在 `.env` 中保留正确值（会覆盖 Secret）。Web 保存设置会写回 `.env`。

或在已安装 `psql` 的机器上（密码勿泄露）：

```bash
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

- [x] SQL Editor 已执行 `20260803120000_initial_goofish_schema.sql`
- [x] 代码已切换为 Postgres-only（`psycopg` 直连）
- [ ] `.env` 已配置 `DATABASE_URL`（仅本机，不提交 Git）
- [ ] 已确认 IPv4：Supabase 直连需网络能访问 `db.*.supabase.co`（企业网需放行或使用 pooler）
- [ ] 重启 API / 爬虫使新配置生效
- [ ] （可选）从历史 `app.sqlite3` 手动迁移数据
