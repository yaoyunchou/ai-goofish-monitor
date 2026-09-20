# 技术方案 / 系统设计

技术文档已统一收录在 **[docs/design/](./design/README.md)** 目录。按「现行 SSOT / 已落地 / 改哪里」检索，不要从架构长文里翻迭代增量。

| 文档 | 说明 |
|------|------|
| [设计文档目录](./design/README.md) | 全部技术方案索引（SSOT / 已落地 / 里程碑 / 归档） |
| [2026-09-20 技术里程碑](./design/milestone-2026-09-20.md) | 已落地模块、调度/删除铁律、下次改代码入口 |
| [系统架构](./design/architecture.md) | 分层架构、进程模型、数据模型（全量；文首有里程碑指针） |
| [采集优先级策略（SSOT）](./design/seller-subscription-collection-strategy.md) | 采谁、先采什么、分几段 |
| [选品预算算法（SSOT）](./design/item-selection-budget.md) | 配额与补位；设计定稿，主采集未接 |
| [店铺分析看板](./design/shop-analytics-subscription-dashboard.md) | `GET /api/shop-analytics/dashboard` |
| [卖家订阅采集方案](./design/seller-subscription-scrape.md) | 风控秒数、无头、调度与实现索引 |
| [商品监控健康度](./design/item-monitor-health.md) | 周健康度；默认 dry-run |
| [PostgreSQL 接入](./design/database-supabase-integration.md) | 数据库连接与迁移 |
| [MySQL 迁移计划（归档）](./design/database-mysql-migration-plan.md) | 已废弃，勿再跟 |
| [产品需求 PRD](./prd/README.md) | 做什么、验收标准 |
