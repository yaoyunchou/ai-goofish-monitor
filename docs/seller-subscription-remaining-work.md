# 卖家订阅主线 · 收尾清单

> 核查日期：2026-09-18
> 基线提交：`6d37bf9` (2026-09-15) feat(seller-subscription)
> 核查方式：git 历史 + 代码逐行核对（本工作区无 venv/pytest，未实跑测试）

## 一、结论

主线功能**已开发完成、可交付**。核心链路（抓取 → 存储 → API → 前端）完整闭环，
全项目无 TODO/FIXME/HACK 遗留。以下 5 项为**边缘收尾**，均不阻塞上线。

| # | 项目 | 类型 | 建议优先级 | 预估改动 |
|---|------|------|-----------|---------|
| 1 | 3 个 API 端点前端未接通 | 功能补全 | P1 | 前端为主 |
| 2 | pacing_json 无前端 UI | 功能补全 | P2 | 前后端小改 |
| 3 | 测试缺口 | 质量 | P1 | 仅测试 |
| 4 | 死函数 has_want_and_view | 清理 | P3 | 1 行删除 |
| 5 | DDL 双轨维护漂移风险 | 技术债 | P2 | 补 migration |

---

## 二、逐项明细

### 1. 前端未接通的 API 端点（P1）

**已确认调用**（`web-ui/src/api/sellerSubscriptions.ts`、`shopAnalytics.ts`）：
- seller-subscriptions：`GET /`、`POST /`、`PATCH /{id}`、`DELETE /{id}`、`PATCH /schedule`、`POST /run`、`GET /items` —— 共 7 个
- shop-analytics：`GET /overview`、`GET /distribution`、`GET /trend`、`POST /collect` —— 共 4 个

**后端已实现但前端零调用**（4 个）：

| 端点 | 位置 | 返回内容 | 价值 |
|------|------|---------|------|
| `GET /api/seller-subscriptions/profiles` | `seller_subscriptions.py:201` | 卖家画像列表 | 中：可与订阅表合并展示店铺等级/粉丝数 |
| `GET /api/seller-subscriptions/metrics` | `seller_subscriptions.py:247` | 单商品时序指标 | **高**：想做「商品价格/想要数趋势图」的唯一数据源 |
| `GET /api/seller-subscriptions/stats` | `seller_subscriptions.py:269` | 商品数/卖家数/调度概况 | 中：可直接做页面顶部概览卡片 |
| `GET /api/shop-analytics/flow` | `shop_analytics.py:58` | 流量明细 | 低：`overview` 已含同类信息 |

**注**：`ShopAnalyticsView.vue` 当前只用了 overview/distribution/trend/collect，
`flow` 属于信息冗余，可考虑后端保留、暂不接线，或直接移除。

**建议动作**：
- 在卖家订阅页顶部加 `stats` 概览卡片 + 商品指标趋势弹窗（接 `metrics`）
- `flow` 端点二选一：接入「流量明细」区块，或从后端删除

---

### 2. pacing_json 前端无 UI（P2）

**现状**：
- 后端完整支持：`seller_subscription_storage.py:281-312`（读写 + JSON 序列化）
- 默认节奏在 `src/domain/seller_subscription_pacing.py`：详情间隔 4–8s、每 10 条批休 60–120s、切换卖家休 2–5 分钟、每 25 条长暂停
- 前端 `SellerSubscriptionView.vue` 仅暴露 `cron`（L231-232）与 `item_limit`（L125-126）
- 前端 TS 接口 `SellerSubscriptionSchedule` **未声明** `pacing_json` 字段

**影响**：用户无法调节采集节奏。爬虫节奏是风控敏感项，固定值无法适配不同场景
（如测试时想加速、被限流时想减速）。

**建议动作**：
1. `sellerSubscriptions.ts` 的 `SellerSubscriptionSchedule` 增加 `pacing_json?: unknown`
2. 视图加「采集节奏」折叠面板：预设「保守/标准/快速」三档 + 高级自定义
3. 或最小方案：仅加一个「启用自定义节奏」开关 + JSON 文本框

---

### 3. 测试缺口（P1）

**现有测试**：
- `tests/unit/test_seller_subscription.py` — seller_ids 解析、item_limit、banner 解析、SQL 适配
- `tests/unit/test_seller_subscription_pacing.py` — 默认值、耗时估算、config 解析、shuffle
- `tests/unit/test_seller_profile_cache.py` — 缓存复用、并发合并
- `tests/integration/test_api_seller_subscriptions.py` — **仅 1 条** CRUD + schedule 用例
- `tests/integration/test_api_shop_analytics.py` — 4 条空态/JSON 兜底

**该测未测**：
| 缺口 | 位置 | 风险 |
|------|------|------|
| 抓取失败重试分支 | `seller_subscription_scraper.py:149-157` except | 高：风控/网络异常是常态，无回归保护 |
| 分页节奏 sleep 序列 | pacing 的 `before_detail`/`after_detail` | 中：仅测了纯函数，未验证实际调用与顺序 |
| `GET /profiles` | `seller_subscriptions.py:201` | 中 |
| `GET /metrics` | `seller_subscriptions.py:247` | 中：趋势图依赖 |
| `GET /stats` | `seller_subscriptions.py:269` | 中：首页概览依赖 |
| 主页头部超时降级 | `scrape_user_profile` 头部失败继续抓列表 | 高：9/15 刚修复的 bug，无测试锁定 |

**建议动作**（按性价比排序）：
1. 补「主页头部超时仍抓列表」的单元测试 —— 直接锁定最近修的 bug
2. 补抓取失败重试分支测试
3. 3 个未覆盖端点各补 1–2 条集成测试（可参照 `test_api_shop_analytics.py` 空态写法）

---

### 4. 死函数（P3）

- `src/domain/seller_ids.py:85` `has_want_and_view()` 仅被测试引用，生产代码零调用
- 原因：scraper 已改用「商品状态 == 在售」过滤（`seller_subscription_scraper.py:121`）
- **动作**：删除函数及其测试用例；若保留，需在 docstring 注明「暂未启用」

---

### 5. DDL 双轨维护（P2）

**现状**：新表 DDL 有两份来源
- Supabase migration：`supabase/migrations/20260915140000_*.sql`、`20260915170000_*.sql`
- 运行时自愈：`storage_bootstrap.py` 的 `ensure_schema`（`CREATE TABLE IF NOT EXISTS`）

**问题**：`seller_subscription_schedule` 的 `pacing_json` / `last_run_*` 列
**只在 ensure_schema 中增量补齐**（`storage_bootstrap.py:142-161`），migration 缺失。
运行时能自愈，但：
- 全新环境走 migration 建表 → 列缺失 → 依赖 ensure_schema 兜底才正常
- 两处 schema 无版本号对齐，长期有漂移风险

**建议动作**：把 `pacing_json` / `last_run_summary` / `last_run_saved` / `last_run_ok` / `last_run_at`
补进对应 migration，并加一条注释说明 ensure_schema 为兼容旧库的兜底。

---

## 三、建议执行顺序

```
第 1 批（最高性价比，直接锁定风险）
  ├─ 补「主页头部超时降级」测试
  ├─ 补抓取失败重试分支测试
  └─ 删除死函数 has_want_and_view + 其测试

第 2 批（功能补全）
  ├─ 卖家订阅页接 stats 概览 + metrics 趋势
  └─ flow 端点决策：接入或删除

第 3 批（体验与技术债）
  ├─ pacing_json 前端 UI（含 TS 类型）
  └─ 补 migration 缺失列
```

## 四、发布前提醒

- 当前分支领先 `origin/master` **2 个提交未推送**，记得 push
- 本工作区未装 venv/pytest，**收尾后请在完整开发环境实跑 `pytest`** 验证
- Postgres 迁移后确认目标库已执行 migration（或依赖 ensure_schema 自愈）
