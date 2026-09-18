# 产品需求文档（PRD）目录

本目录集中存放 **software-company** 工作流产出的 PRD 与需求基线。每条 PRD 对应一个可独立评审的产品/专题。

| 文档 | 状态 | 说明 |
|------|------|------|
| [卖家订阅大规模采集 · 风控与运营策略](./seller-subscription-anti-risk.md) | **已部分交付** | 降速分批、多账号分工、采集调度无头模式；IP 轮换不在本期范围 |
| [卖家订阅采集优先级（设计 SSOT）](../design/seller-subscription-collection-strategy.md) | **现行「先采谁」** | 采集阶段与排序以设计 SSOT 为准；改逻辑先改该文再改代码 |
| [店铺数据 · 卖家订阅看板](./shop-analytics-subscription-dashboard.md) | **已交付** | 将 `/shop-analytics` 从空罗盘改为订阅日指标分析页 |
| [项目健康度与缺口分析](./project-health.md) | 基线 / 持续更新 | 文档·测试·CI 缺口审计与五阶段整改计划（2026-09-16 起） |

## 约定

- **新 PRD**：`docs/prd/<主题英文短名>.md`，在本 README 登记一行
- **与实现联动**：PRD 内「交付状态」随版本更新；细节以 `docs/features.md`、`docs/user-guide.md` 为准
- **采集顺序**：卖家订阅的阶段与优先级以 [`docs/design/seller-subscription-collection-strategy.md`](../design/seller-subscription-collection-strategy.md) 为准，PRD 不另维护第二份规则
- **计划来源**：Cursor Plan 经 PM 整理后写入本目录，不保留仅在 Plan 中的草稿

## 相关链接

- [功能文档](../features.md)
- [用户使用指南](../user-guide.md)
- [技术方案目录](../design/README.md)
- [系统架构](../design/architecture.md)
