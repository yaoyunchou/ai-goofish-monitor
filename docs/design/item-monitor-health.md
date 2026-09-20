# 商品监控健康度与自动停用

> 状态：**已交付（默认安全空跑）** · 关联 PRD：[`docs/prd/item-monitor-health.md`](../prd/item-monitor-health.md)  
> 关联功能文档：[`docs/features.md` §2.12 / §3.12 / §12.6](../features.md)  
> **归档**：2026-09-20 见 [milestone-2026-09-20.md](./milestone-2026-09-20.md)

## 1. 背景与目标

卖家订阅长期运行后，`seller_item_daily_metrics` 会持续增长，但其中相当一部分商品「浏览量 + 想要数」长期不动 —— 它们持续消耗采集配额（每家店有每轮上限、有风控节奏），却没有带来任何有效信息。

**目标**：以 **自然周** 为周期，自动识别「浏览和想要都低、且没有明显增长」的商品，**停止对它的监控**，把配额让给更值得盯的商品。

**非目标**：

- **不删除任何数据**。停用只影响"是否继续采集"，`seller_item_daily_metrics` 历史行完整保留。
- 不做可视化看板/图表（本期只做判定 + 停用 + 通知 + 恢复接口）。
- 不改动关键词任务的启停逻辑（那是 `tasks` 表，与卖家订阅互不相干）。

## 2. 为什么不是操作 `tasks` 表

调研阶段的一个重要纠正：卖家订阅 **不经过 `tasks` 表**。

- `seller_item_daily_metrics.task_name` 是**硬编码常量** `SELLER_SUBSCRIPTION_TASK_NAME = "seller_subscriptions"`，不是每个订阅一条任务记录。
- 采集由独立子进程 + 全局单例调度（`seller_subscription_schedule` id=1）驱动，见 `src/services/process_service.py`。

因此「停用某个商品的监控」必须落在一张 **按商品粒度** 的表上。原 `seller_subscription_items` 有 `item_status`，但那是闲鱼侧的「在售/已售」状态，**不是** 监控开关，不能复用。

→ 新增 `seller_subscription_items.is_muted` 作为监控开关。

## 3. 数据模型

### 3.1 `seller_subscription_items` 新增列

```sql
ALTER TABLE seller_subscription_items
  ADD COLUMN IF NOT EXISTS is_muted      BOOLEAN     NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS muted_at      TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS muted_reason  TEXT,
  ADD COLUMN IF NOT EXISTS muted_week    DATE;

CREATE INDEX IF NOT EXISTS idx_ssi_muted
  ON seller_subscription_items (is_muted)
  WHERE is_muted = TRUE;
```

| 列 | 语义 |
|----|------|
| `is_muted` | 监控开关。`TRUE` = 不再采集 |
| `muted_at` | 停用时刻 |
| `muted_reason` | 人类可读原因（含当周数据摘要） |
| `muted_week` | 触发停用的那一周（周一日期），便于回溯与「同一周不重复处理」 |

### 3.2 `item_monitor_health_weekly`（判定明细表）

每周每商品一行，**无论最终是保留还是停用都落库** —— 这样空跑期也能积累可观察的判定结果。

```sql
CREATE TABLE item_monitor_health_weekly (
  id              BIGSERIAL PRIMARY KEY,
  week_start      DATE        NOT NULL,
  week_end        DATE        NOT NULL,
  seller_user_id  TEXT        NOT NULL,
  item_id         TEXT        NOT NULL,
  title           TEXT,
  days_with_data  INTEGER     NOT NULL DEFAULT 0,
  view_start      INTEGER,
  view_end        INTEGER,
  view_growth     INTEGER,
  want_start      INTEGER,
  want_end        INTEGER,
  want_growth     INTEGER,
  healthy         BOOLEAN     NOT NULL,
  reason          TEXT,
  action          TEXT        NOT NULL,
  decided_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (week_start, seller_user_id, item_id)
);
```

`action` 枚举：`kept` / `muted` / `dry_run` / `skipped` / `interrupted`。

> **双写约定**：与项目既有模式一致，迁移 SQL 放在 `supabase/migrations/20260918000000_item_monitor_health.sql`，同时在 `src/infrastructure/persistence/db_connection.py::_INCREMENTAL_SCHEMA_STATEMENTS` 追加等价语句，保证老库启动时自动补列/补表。

## 4. 判定算法

### 4.1 周期

固定自然周，`Asia/Shanghai`，周一 00:00 ~ 周日 23:59。判定**上一个完整周**。

```python
def last_full_week(today: date | None = None) -> tuple[date, date]:
    current = today or shanghai_today()
    this_monday = current - timedelta(days=current.weekday())
    last_monday = this_monday - timedelta(days=7)
    return last_monday, last_monday + timedelta(days=6)
```

### 4.2 增长计算（SQL）

用 3 个 CTE + `DISTINCT ON` 取周内**最早**与**最晚**快照，求增量：

```
first_seen  -- DISTINCT ON (task, seller, item) ... ORDER BY snapshot_day ASC
last_seen   -- DISTINCT ON (task, seller, item) ... ORDER BY snapshot_day DESC
span        -- JOIN 两者，COALESCE 处理缺值，LEFT JOIN items 取 title
```

周内只有 1 天数据 → 在 Python 侧 **丢弃**（`first_day >= last_day`），因为单点无法计算增长。

> 为什么不用窗口函数？项目既有 `seller_item_daily_storage` 都是朴素 SQL + Python 后处理，保持一致可读性更好。

### 4.3 决策优先级（自上而下短路）

| 序 | 条件 | 结果 |
|----|------|------|
| 1 | `days_with_data < min_days_with_data` | `skipped`（数据不足，不判定） |
| 2 | 已 `is_muted` | `skipped` |
| 3 | 首/末快照 `want_count` 或 `view_count` 为 NULL | `skipped`（缺指标） |
| 4 | 末笔数据距 `week_end` 超出容差 | `interrupted`（**不停用**） |
| 5 | `first_seen_at` 距今 < `protect_days` | `skipped`（新品保护期） |
| 6 | `view_growth >= keep_view_growth` **OR** `want_growth >= keep_want_growth` | `kept` |
| 7 | 否则 | `muted` |

**第 4 条是最关键的一条**：采集只覆盖「在售」商品，商品一旦售出就会自然退出采集范围，数据"断流"。如果把「没数据」当成「不健康」，会把卖得最好的商品全部停掉。因此中断一律 **放行不停用**。

### 4.4 配置

见 `docs/features.md` §12.6。全部通过环境变量注入 `MonitorConfig`，默认值 **安全**：

```python
auto_disable_enabled: bool = False   # 总开关，默认关了
dry_run: bool = True                 # 空跑，只判定不执行
keep_view_growth: int = 10
keep_want_growth: int = 2
min_days_with_data: int = 2
protect_days: int = 14
max_mute_per_week: int = 0           # 0 = 不限
```

## 5. 执行链路

```
APScheduler (item_monitor_health_weekly, cron 0 9 * * 1)
  └─ scheduler_service._run_monitor_health_check()
       └─ item_monitor_health_service.run_weekly_check(week_start, week_end, dry_run, notify)
            1. weekly_item_growth_sync()      读周增量
            2. evaluate_week()                逐商品判定 → [ItemHealthDecision]
            3. 写 item_monitor_health_weekly   判定明细（含 kept/dry_run）
            4. 应用 max_mute_per_week 上限      按"最差"排序截断
            5. mute_items_sync()              置 is_muted（仅当 dry_run=False）
            6. 通知                            汇总一条消息（停用数 + 清单）
```

### 5.1 采集侧过滤

`seller_subscription_scraper` 在 **`_split_items_by_today_coverage()` 之前** 过滤已停用商品：

```python
try:
    muted_ids = load_muted_item_ids_sync(user_id)
except Exception as exc:
    print(f"   [警告] 读取已停用商品失败，本轮不过滤: {exc}")
    muted_ids = set()
```

**顺序很重要**：先过滤，再拆分「今天已采/未采」，否则已停用商品会计入覆盖率统计，导致每轮都报告"未覆盖"。

**try/except 是刻意的**：数据库抖动绝不能让整个采集任务失败。降级为"不过滤"（多采一轮）远比"采集崩掉"可接受。

## 6. 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/seller-subscriptions/items/health` | 周判定结果（`week_start` / `action` / `limit`） |
| POST | `/api/seller-subscriptions/items/health/run` | 手动触发（`week_start` / `week_end` / `dry_run` / `notify`） |
| POST | `/api/seller-subscriptions/items/{item_id}/restore` | 恢复监控 |

> ⚠️ **路由顺序**：`GET /items/health` 必须声明在 `GET /items/{item_id}/detail` 之前，否则 FastAPI 会把 `health` 当成 `item_id`。回归用例已覆盖。

## 7. 只读体检脚本

上线前用真实数据校准阈值：

```bash
python -m scripts.item_metric_health_check [--weeks N]
```

输出 T1–T8 共 8 张报告：总行数/日期范围、NULL 与零值占比、有数据天数分布、增长直方图、各阈值下会停用的商品数、数据中断清单、负增长清单、按卖家汇总 + 阈值敏感性扫描。

**严格只读（仅 SELECT）**，用于回答"阈值定 10/2 合适吗"这类问题。

## 8. 交付与验证

| 项 | 位置 |
|----|------|
| 判定服务 | `src/services/item_monitor_health_service.py` |
| 存储层 | `src/services/seller_item_daily_storage.py`（`_WEEKLY_GROWTH_SQL` / `weekly_item_growth_sync` / `load_muted_item_ids_sync` / `mute_items_sync`） |
| 调度 | `src/services/scheduler_service.py`（`reload_monitor_health_job`，**单例、不被 `reload_jobs` 调用**） |
| 生命周期挂载 | `src/app.py`（lifespan 内，在 `reload_jobs()` 之前） |
| 采集过滤 | `src/seller_subscription_scraper.py` |
| 迁移 | `supabase/migrations/20260918000000_item_monitor_health.sql` + `db_connection.py` 增量语句 |
| 体检脚本 | `scripts/item_metric_health_check.py` |
| 测试 | `tests/unit/test_item_monitor_health_service.py`（28）/ `test_item_weekly_growth.py`（23）/ `test_seller_item_health_routes.py`（7） |

## 9. 上线路径（务必按序）

1. 配好 `DATABASE_URL`，跑体检脚本看真实分布 → 校准 `MONITOR_KEEP_*`
2. 保持默认（关闭 + 空跑），观察 1~3 周的 `item_monitor_health_weekly` 判定结果
3. 若判定与实际预期一致，再 `MONITOR_AUTO_DISABLE_ENABLED=true` + `MONITOR_DRY_RUN=false`
4. 建议同时设 `MONITOR_MAX_MUTE_PER_WEEK`，给误判留缓冲

## 10. 后续可做

- Web UI：商品列表加「已停用」筛选与恢复按钮；健康度明细页
- 阈值按卖家自适应（不同店铺流量量级差异大）
- 停用后定期"复活"探针：每 N 周重采一次，若指标回升自动解除停用
- 把 `interrupted` 与采集失败率联动，区分"已售出"与"采集故障"
