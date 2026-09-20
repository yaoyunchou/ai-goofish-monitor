# 技术里程碑快照 · 2026-09-20

> **文档性质**：design 侧归档（架构师 高见远）。冻结「现行 SSOT / 已落地模块 / 改哪里」。  
> **日期**：2026-09-20  
> **不做**：新功能任务分解；不复制 [architecture.md](./architecture.md) 全文。  
> **全量架构**仍以 `architecture.md` 为准；**采集顺序**以 [seller-subscription-collection-strategy.md](./seller-subscription-collection-strategy.md) 为唯一策略源。  
> **产品里程碑**：[docs/prd/milestone-2026-09-20.md](../prd/milestone-2026-09-20.md)

---

## 1. 归档说明

本期卖家订阅主线（三阶段采集、订阅日指标看板、调度不被卸、删除级联、周健康度默认 dry-run）**已落地**。选品预算算法 **设计定稿**，仅有 simulate，**未接入** scraper 主路径。

下次新需求开工前：先读本文找入口，再改对应 SSOT，最后改代码。验证只用 `pytest` / `npx vue-tsc -b --noEmit` / `npx vitest run`，**禁止起服务**。

---

## 2. SSOT 地图（哪篇回答哪个问题）

| 问题 | 现行 SSOT | 不要去哪找 |
|------|-----------|------------|
| 采谁、先采什么、分几段、覆盖判定 | [seller-subscription-collection-strategy.md](./seller-subscription-collection-strategy.md) | scrape / PRD / 代码注释另写一套顺序 |
| 风控秒数、无头、账号分工、表与订阅 API | [seller-subscription-scrape.md](./seller-subscription-scrape.md) | 策略文重复 pacing 数字 |
| 看板字段口径、空心日、`GET /dashboard` | [shop-analytics-subscription-dashboard.md](./shop-analytics-subscription-dashboard.md) + 策略文 **§5.4** | `GET /stats` 的 `len()`；`seller_profiles.item_count`；datacompass |
| 周健康度、`is_muted`、默认空跑 | [item-monitor-health.md](./item-monitor-health.md) | `tasks` 表启停（订阅不走 tasks） |
| 每店配额、踢出与补位（保量） | [item-selection-budget.md](./item-selection-budget.md) | 尚未进 scraper；勿在策略文另写配额公式 |
| 分层、进程、关键词爬虫、部署 | [architecture.md](./architecture.md) | 按迭代整篇改写本文档 |
| PostgreSQL / Supabase 连接与迁移 | [database-supabase-integration.md](./database-supabase-integration.md) | MySQL 方案 |
| MySQL | [database-mysql-migration-plan.md](./database-mysql-migration-plan.md)（**已归档，废弃**） | 新需求继续跟 MySQL |

专题索引：[README.md](./README.md)。兼容入口：[docs/design.md](../design.md)。

---

## 3. 已落地模块 + 文件索引

### 3.1 三阶段采集（阶段零对齐列表 → 阶段一今日未采 → 阶段二刷新已有）

| 角色 | 路径 |
|------|------|
| 主流程 | `src/seller_subscription_scraper.py`（`scrape_registered_seller_subscriptions` / `_scrape_seller_ids`） |
| 店序 / 钩子 | `src/domain/seller_subscription_pacing.py` |
| 策略单测 | `tests/unit/test_seller_subscription_priority_strategy.py` |
| 节奏单测 | `tests/unit/test_seller_subscription_pacing.py` |
| 入口 | Cron / `POST /api/seller-subscriptions/run` / `spider_v2.py --seller-subscriptions` |
| 虚拟任务 | `SELLER_SUBSCRIPTION_TASK_NAME = "seller_subscriptions"`，job id `-1`，日志 `logs/seller_subscriptions_-1.log` |

硬顺序：阶段零结束前不得 `fetch_item_detail`。细节只改 collection-strategy，再改上表。

### 3.2 店铺分析看板

| 角色 | 路径 |
|------|------|
| API | `GET /api/shop-analytics/dashboard?period=today\|7d`（`src/api/routes/shop_analytics.py`） |
| 聚合存储 | `src/services/shop_analytics_dashboard_storage.py` |
| 领域模型 | `src/domain/shop_analytics_dashboard.py` |
| 前端页 | `web-ui/src/views/ShopAnalyticsView.vue` |
| 前端 API | `web-ui/src/api/shopAnalytics.ts` |
| 子组件 | `web-ui/src/components/shop-analytics/ShopRankingTable.vue`、`HotItemsTable.vue` |
| 单测 | `tests/unit/test_shop_analytics_dashboard.py`、`tests/unit/test_shop_analytics_api.py` |

主页面只打 `/dashboard`。旧 datacompass（`/overview` `/flow` `/distribution` `/trend`、`POST /collect`）保留兼容，**不进主看板**。口径见看板文 + 策略 §5.4：监控商品 ≠ 店铺商品总数；近 7 天想要/浏览取锚点日合计，不跨日求和；空心日 `null` 不得补 0。

### 3.3 调度不被卸掉

| 角色 | 路径 |
|------|------|
| 调度 | `src/services/scheduler_service.py` |
| 生命周期 | `src/app.py` `lifespan` |
| 下次执行 | `get_seller_subscription_next_run_time()` → API `next_run_at`（`src/api/routes/seller_subscriptions.py`） |
| 采集控制台 | `web-ui/src/views/SellerCollectionView.vue` |
| 单测 | `tests/unit/test_scheduler_service.py`、`tests/unit/test_seller_subscription_schedule.py` |

独立 job：

| job id | 含义 | 谁挂上 |
|--------|------|--------|
| `seller_subscriptions` | 订阅采集 | `reload_seller_subscription_job` |
| `item_monitor_health_weekly` | 周健康度 | `reload_monitor_health_job` |
| `task_{id}` | 关键词任务 | `reload_jobs` |

`reload_jobs` **只删** `task_*`，**禁止** `remove_all_jobs`。

### 3.4 删除级联

| 角色 | 路径 |
|------|------|
| 入口 | `delete_subscription_with_stats_sync`（`src/services/seller_subscription_storage.py`） |
| 关联表常量 | `SELLER_RELATED_TABLES`：`seller_subscription_items`、`seller_item_daily_metrics`、`seller_item_metrics`、`item_monitor_health_weekly`、`seller_profiles`、`item_detail_api_raw` |
| raw 反查 | 先取 `seller_item_daily_metrics.raw_record_id`，再删 `crawl_raw_records`（该表无 `seller_user_id`） |
| 列表过滤 | `SQL_ITEM_BELONGS_TO_SUBSCRIPTION` / `_SQL_LEGACY_ITEM_SUBSCRIBED`：`EXISTS` 仍在 `seller_subscriptions` 的卖家 |
| 单测 | `tests/unit/test_seller_subscription_delete_cascade.py`、`tests/integration/test_seller_subscription_delete_cascade_e2e.py` |

顺序：查出 `seller_user_id` → 清关联（含 raw）→ 再删订阅行。同一事务。

### 3.5 商品监控健康度（已交付，默认 dry-run）

| 角色 | 路径 |
|------|------|
| 判定服务 | `src/services/item_monitor_health_service.py`（`MONITOR_DRY_RUN` 默认 **true**） |
| 存储 | `src/services/seller_item_daily_storage.py`（周增长 SQL / mute） |
| 调度 | `reload_monitor_health_job`，**不被** `reload_jobs` 调用 |
| 挂载 | `src/app.py` lifespan，在 `reload_jobs()` **之前** |
| 采集过滤 muted | `src/seller_subscription_scraper.py` |
| 迁移 | `supabase/migrations/20260918000000_item_monitor_health.sql` |
| 体检（只读） | `scripts/item_metric_health_check.py` |
| API | `GET/POST .../items/health`、`POST .../items/{item_id}/restore` |
| 单测 | `tests/unit/test_item_monitor_health_service.py`、`test_item_weekly_growth.py`、`test_seller_item_health_routes.py` |

默认安全空跑：判定入库 `action=dry_run`，不真正 mute。真正停用需显式 `MONITOR_AUTO_DISABLE_ENABLED=true` 且 `MONITOR_DRY_RUN=false`（见健康度文 §9）。**未做**：默认真正 mute。

### 3.6 选品预算（设计定稿，主路径未接）

| 角色 | 路径 | 状态 |
|------|------|------|
| 算法 SSOT | [item-selection-budget.md](./item-selection-budget.md) v4 | 定稿 |
| 只读模拟 | `scripts/item_selection_simulate.py` | 已交付 |
| 模拟单测 | `tests/unit/test_item_selection_simulate.py` | 已交付 |
| scraper / 配额主路径 | `src/seller_subscription_scraper.py` 等 | **未开工（S1–S5）** |

---

## 4. 两条铁律

### 4.1 调度

1. `SchedulerService.reload_jobs` **不得** `remove_all_jobs`；只移除 `id` 以 `task_` 开头的关键词 job。
2. `lifespan` 顺序必须是：`reload_seller_subscription_job` → `reload_monitor_health_job` → `reload_jobs`（关键词）→ `scheduler.start()`。先挂订阅（及健康度）单例，再刷 keyword jobs。
3. 订阅下次执行读进程内 job：`get_seller_subscription_next_run_time()` → `next_run_at`；job 未挂上为 `null`，UI 提示保存调度或重启后端，不要用库表臆造 cron 下次时间冒充已挂载。

### 4.2 删除

1. 删除订阅必须 **先清关联再删订阅行**（`delete_subscription_with_stats_sync`）。先丢订阅行就丢 `seller_user_id`，关联与 raw 变孤儿。
2. 商品/日指标列表必须 `EXISTS` **仍订阅** 的卖家；删订阅后不得继续出现在监控列表。
3. `crawl_raw_records` 不在 `SELLER_RELATED_TABLES`：必须先从日指标反查 `raw_record_id` 再删。

---

## 5. 未接入设计 / 技术 backlog

| 项 | 状态 | 下次入口 |
|----|------|----------|
| 选品预算接入 scraper（S1–S5） | 设计 + simulate only | 先改 [item-selection-budget.md](./item-selection-budget.md)，再改 scraper / 健康度 mute 联动 |
| IP 轮换 | 未做 | scrape / `src/rotation.py`；PRD 已声明不在采集主线范围 |
| datacompass 进主看板 | 明确不做（本期） | 看板文：旧 API 保留；主页面禁止揉进 `/dashboard` |
| Cron misfire 补跑 | 未做 | `scheduler_service.py`；不得用 `remove_all_jobs` 偷懒重建 |
| 健康度默认真正 mute | 未做 | 先改 [item-monitor-health.md](./item-monitor-health.md) 上线路径，再改默认 env |

---

## 6. 改代码纪律（下次开工必守）

| 要改的内容 | 先改 | 再改 |
|------------|------|------|
| 采集顺序 / 阶段 / 覆盖判定 | collection-strategy | `seller_subscription_scraper.py`、`seller_subscription_pacing.py`、`test_seller_subscription_priority_strategy.py` |
| 选品 / 每店配额 / 补位 | item-selection-budget | 业务代码（当前无主路径实现） |
| 风控秒数 / `DEFAULT_PACING` / `pacing_json` | **只写** seller-subscription-scrape | `seller_subscription_pacing.py`；**不要**在策略文重复秒数 |
| 看板口径 / 空心日 / 双轴 | shop-analytics-subscription-dashboard + 策略 §5.4 | `shop_analytics_dashboard_storage.py`、`ShopAnalyticsView.vue` |
| 周健康度阈值 / dry-run 默认 | item-monitor-health | `item_monitor_health_service.py` |
| 调度卸载 / job 生命周期 | 本文 §4.1 + architecture 进程模型 | `scheduler_service.py`、`src/app.py` |
| 删除级联 | 本文 §4.2 | `seller_subscription_storage.py` |

验证：**禁止** `start.sh` / `python -m src.app` / `npm run dev` / `uvicorn` / `docker compose up` / `spider_v2.py`。用 `pytest`、`npx vue-tsc -b --noEmit`、`npx vitest run`。本地端口 **8010**；**不要动 8000**。

---

## 7. 下次改代码入口（速查）

```text
改采集顺序     → docs/design/seller-subscription-collection-strategy.md
改风控秒数     → docs/design/seller-subscription-scrape.md
改看板口径     → docs/design/shop-analytics-subscription-dashboard.md  +  策略 §5.4
改健康度       → docs/design/item-monitor-health.md
改选品/配额    → docs/design/item-selection-budget.md   （主路径尚未接线）
找分层/进程    → docs/design/architecture.md
找本期落地哪   → 本文 §3
调度 / 删除    → 本文 §4（铁律，先读再改）
```
