# Supabase（PostgreSQL）接入指南

项目：**wkhatdhgohkpsqkytotz**  
Dashboard：[Project Settings](https://supabase.com/dashboard/project/wkhatdhgohkpsqkytotz/settings/general)

应用**仅使用 PostgreSQL**：在 `.env` 配置 `DATABASE_URL`（推荐 **Session pooler**）。架构：**Vue → FastAPI → PostgreSQL**（`psycopg`）。

---

## 1. 建表

在 [SQL Editor](https://supabase.com/dashboard/project/wkhatdhgohkpsqkytotz/sql/new) 执行：

`supabase/migrations/20260803120000_initial_goofish_schema.sql`

或使用 Supabase CLI：`supabase link` + `supabase db push`。

---

## 2. 连接串

Dashboard → **Connect** → **Session pooler** → URI，填入 **Database password** 后复制。

| 模式 | 说明 |
|------|------|
| Session pooler | 多进程 / Cloud 推荐，`postgres.<project-ref>@...pooler...:5432` |
| Direct | 仅当网络可达 `db.*.supabase.co`（部分环境仅 IPv6） |

### `.env`（勿提交密码）

```env
DATABASE_URL=postgresql+asyncpg://postgres.wkhatdhgohkpsqkytotz:[PASSWORD]@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres
```

密码是 **Database password**，不是 `anon` / `service_role` JWT。

### 配置优先级

1. 仓库 `.env`（`env_manager` 优先）
2. 进程环境变量（如 Cursor Secrets，仅当 `.env` 无该键）

---

## 3. 自检与启动

```bash
pip install -r requirements.txt
python3 -m scripts.verify_database   # 应显示 连接: OK
python3 -m src.app
```

表为空时，启动会尝试从 `config.json` / `jsonl/` / `price_history/` **导入一次**（bootstrap）。

---

## 4. 可选：从旧 SQLite 文件导入历史数据

**不需要老数据可跳过。**

```bash
python3 -m scripts.migrate_sqlite_to_postgres --source data/app.sqlite3 --dry-run
python3 -m scripts.migrate_sqlite_to_postgres --source data/app.sqlite3
```

---

## 5. 检查清单

- [x] 运行时仅 Postgres（无 `DATABASE_DRIVER` / `APP_DATABASE_FILE`）
- [ ] SQL 已执行 `20260803120000_initial_goofish_schema.sql`
- [ ] `.env` 已配置 `DATABASE_URL`
- [ ] `python3 -m scripts.verify_database` 通过
- [ ] （可选）旧 `app.sqlite3` 已迁移或丢弃

---

## 6. API Keys 说明

| 密钥 | 本项目 |
|------|--------|
| Database 连接串 | **业务表读写（必配）** |
| `anon` / `service_role` | 不必用于监控业务表 |

业务表已启用 RLS 且无开放策略；后端用 Database 连接串不受 PostgREST 限制。
