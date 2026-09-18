# Supabase（PostgreSQL）接入指南

项目：**goodfish-sg**（`vcojlixcuqinanjlflgd`，新加坡 `ap-southeast-1`）  
Dashboard：[Project Settings](https://supabase.com/dashboard/project/vcojlixcuqinanjlflgd/settings/general)

> 旧东京项目 `wkhatdhgohkpsqkytotz` 数据已迁移，可在 Dashboard 暂停以节省免费配额。

应用**仅使用 PostgreSQL**：在 `.env` 配置 `DATABASE_URL`（推荐 **Session pooler**）。架构：**Vue → FastAPI → PostgreSQL**（`psycopg`）。

---

## 1. 建表

在 [SQL Editor](https://supabase.com/dashboard/project/wkhatdhgohkpsqkytotz/sql/new) 执行：

`supabase/migrations/20260803120000_initial_goofish_schema.sql`

卖家订阅与店铺罗盘还需执行（按时间顺序）：

- `20260915140000_seller_subscription_and_datacompass.sql` — `task_type`、卖家画像/商品指标、datacompass 快照表
- `20260915170000_seller_subscription_registry.sql` — 独立 `seller_subscriptions` 注册表与全局调度
- `20260916170000_item_detail_api_raw.sql` — 商品详情 API 原始数据（如有）

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
DATABASE_URL=postgresql+asyncpg://postgres.vcojlixcuqinanjlflgd:[PASSWORD]@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres
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

## 5. 卖家订阅与店铺罗盘相关表

| 表 | 说明 |
|----|------|
| `seller_subscriptions` | 独立卖家订阅列表（`seller_user_id` 唯一） |
| `seller_subscription_schedule` | 全局 Cron/限额/账号策略（单行 id=1） |
| `seller_profiles` | 卖家画像快照（`profile_day` 日级 UPSERT） |
| `seller_subscription_items` | 订阅商品静态主表 |
| `seller_item_daily_metrics` | 商品日指标；`raw_record_id` UNIQUE FK → `crawl_raw_records` |
| `crawl_raw_records` | 通用爬虫原始数据（created_at / updated_at / raw_json） |
| `seller_item_metrics` | （遗留）旧时序表，新写入已停用 |
| `shop_datacompass_snapshots` | 工作台 datacompass API 快照 |

`tasks.task_type`：`keyword_search`（默认）| `seller_subscription` | `shop_datacompass`。

自检时可确认上述表存在且 RLS 已启用（后端通过 Database 连接串读写）。

## 6. 检查清单

- [x] 运行时仅 Postgres（无 `DATABASE_DRIVER` / `APP_DATABASE_FILE`）
- [ ] SQL 已执行初始 schema + 卖家订阅/罗盘迁移
- [ ] `.env` 已配置 `DATABASE_URL`
- [ ] `python3 -m scripts.verify_database` 通过
- [ ] （可选）旧 `app.sqlite3` 已迁移或丢弃

---

## 7. API Keys 说明

| 密钥 | 本项目 |
|------|--------|
| Database 连接串 | **业务表读写（必配）** |
| `anon` / `service_role` | 不必用于监控业务表 |

业务表已启用 RLS 且无开放策略；后端用 Database 连接串不受 PostgREST 限制。
