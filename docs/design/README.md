# 技术方案 / 系统设计目录

本目录集中存放 **架构、数据库、采集链路** 等技术设计文档，与 [`docs/prd/`](../prd/README.md)（产品需求）分工：

| 目录 | 回答的问题 |
|------|------------|
| `docs/prd/` | **做什么**、为什么、验收标准 |
| `docs/design/` | **怎么做**、模块边界、数据流、表结构、实现索引 |

## 文档索引

| 文档 | 说明 |
|------|------|
| [系统架构](./architecture.md) | 分层架构、进程模型、核心链路、前端架构、设计决策 |
| [卖家订阅采集优先级策略（SSOT）](./seller-subscription-collection-strategy.md) | **采集优先级唯一策略源**；改逻辑先改此文，再改 scraper/pacing 与 `test_seller_subscription_priority_strategy.py` |
| [店铺分析看板（订阅日指标）](./shop-analytics-subscription-dashboard.md) | `/shop-analytics` 主数据源改为 `seller_item_daily_metrics`；`GET /dashboard` 聚合接口 |
| [卖家订阅采集技术方案](./seller-subscription-scrape.md) | 风控节奏、无头模式、账号分工、表与 API（对应 PRD）；**不要**在此重复写采集顺序 |
| [PostgreSQL / Supabase 接入](./database-supabase-integration.md) | 连接、建表、迁移、自检 |
| [MySQL 迁移计划（归档）](./database-mysql-migration-plan.md) | 历史方案，已由 PostgreSQL 取代 |

### 页面与 API 探索（调研向）

| 文档 | 说明 |
|------|------|
| [C 端用户主页探索](../exploration/personal-profile-exploration.md) | `personal` 页 MTOP API、与 `scrape_user_profile` 对齐 |
| [卖家工作台探索](../exploration/seller-workbench-exploration.md) | datacompass API、店铺数据罗盘 |

> 探索文档保留在 `docs/exploration/`（含截图与快照 JSON），本目录通过链接引用。

## 约定

- **新方案**：`docs/design/<主题英文短名>.md`，在本 README 登记
- **与 PRD 联动**：PRD 写目标与验收；本目录写模块、接口、数据模型与实现路径
- **架构师产出**：software-company 流程中架构师默认写入 `docs/design/<feature>.md`；全量架构维护在 `architecture.md`
- **兼容入口**：[`docs/design.md`](../design.md)

## 相关链接

- [PRD 目录](../prd/README.md)
- [功能文档](../features.md) — 已实现能力清单
- [项目说明](../project-overview.md)
