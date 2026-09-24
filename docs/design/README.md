# 技术方案 / 系统设计目录

本目录集中存放 **架构、数据库、采集链路** 等技术设计文档，与 [`docs/prd/`](../prd/README.md)（产品需求）分工：

| 目录 | 回答的问题 |
|------|------------|
| `docs/prd/` | **做什么**、为什么、验收标准 |
| `docs/design/` | **怎么做**、模块边界、数据流、表结构、实现索引 |

**先看哪份**：现行规则看下方「SSOT」；落地文件看「已落地专题」；2026-09-20 冻结点看 [里程碑快照](./milestone-2026-09-20.md)。不要从 `architecture.md` 里翻迭代增量。

## 现行 SSOT（改逻辑先改文）

| 文档 | 回答什么 | 改代码前 |
|------|----------|----------|
| [卖家订阅采集优先级策略](./seller-subscription-collection-strategy.md) | **采谁、先采什么、分几段**（唯一策略源） | 再改 scraper / pacing / `test_seller_subscription_priority_strategy.py` |
| [选品预算算法](./item-selection-budget.md) | 每店配额、踢出与补位（路线 A） | 再改业务代码。**设计定稿，主采集未接**（仅 `scripts/item_selection_simulate.py`） |
| [店铺分析看板](./shop-analytics-subscription-dashboard.md) | `GET /dashboard` 字段与空心日 | 口径同时对齐策略文 **§5.4**（监控商品 ≠ 店铺商品总数） |
| [卖家订阅采集技术方案](./seller-subscription-scrape.md) | 风控秒数、无头、账号、表与 API | **不要**在策略文重复 pacing 数字 |
| [多渠道并行执行](./channel-execution.md) | 同渠道排队、跨渠道并行；定时入队，手动 409 | **改执行顺序先改这篇再改代码** |

## 已落地专题

| 文档 | 说明 |
|------|------|
| [系统架构](./architecture.md) | 分层、进程、核心链路、前端、设计决策；文首链到本期里程碑 |
| [商品监控健康度](./item-monitor-health.md) | 周健康度 / `is_muted`；**已交付，默认 `MONITOR_DRY_RUN=true`** |
| [小红书公开商品监控](./xhs-monitor.md) | 表、高水位、独立 Cron `xhs_monitor` |
| [变化算法对照](./metric-delta-comparison.md) | 闲鱼周差值 vs 小红书高水位；本期不改闲鱼 |
| [PostgreSQL / Supabase 接入](./database-supabase-integration.md) | 连接、建表、迁移、自检 |

## 里程碑快照

| 文档 | 说明 |
|------|------|
| [2026-09-20 技术里程碑](./milestone-2026-09-20.md) | 已落地模块文件索引、调度/删除铁律、未接入设计、下次改代码入口 |

## 归档

| 文档 | 说明 |
|------|------|
| [MySQL 迁移计划（归档）](./database-mysql-migration-plan.md) | 历史方案，已由 PostgreSQL 取代；新需求不要再跟 |

### 页面与 API 探索（调研向）

| 文档 | 说明 |
|------|------|
| [C 端用户主页探索](../exploration/personal-profile-exploration.md) | `personal` 页 MTOP API、与 `scrape_user_profile` 对齐 |
| [卖家工作台探索](../exploration/seller-workbench-exploration.md) | datacompass API、店铺数据罗盘 |

> 探索文档保留在 `docs/exploration/`（含截图与快照 JSON），本目录通过链接引用。datacompass **不进** 现行主看板。

## 约定

- **新方案**：`docs/design/<主题英文短名>.md`，在本 README 登记
- **与 PRD 联动**：PRD 写目标与验收；本目录写模块、接口、数据模型与实现路径
- **架构师产出**：software-company 流程中架构师默认写入 `docs/design/<feature>.md`；全量架构维护在 `architecture.md`（按迭代只加指针/附录，不整篇重写）
- **改采集顺序**：先改 collection-strategy，再改代码
- **改选品/配额**：先改 item-selection-budget，再改代码
- **验证**：`pytest` / `vue-tsc` / `vitest`；禁止起服务占端口
- **兼容入口**：[`docs/design.md`](../design.md)

## 相关链接

- [PRD 目录](../prd/README.md)
- [2026-09-20 需求里程碑](../prd/milestone-2026-09-20.md)
- [功能文档](../features.md) — 已实现能力清单
- [项目说明](../project-overview.md)
