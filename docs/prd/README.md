# 产品需求文档（PRD）目录

本目录集中存放 **software-company** 工作流产出的 PRD 与需求基线。每条 PRD 对应一个可独立评审的产品/专题。

**2026-09-20**：本期能力已冻结为 [里程碑需求快照](./milestone-2026-09-20.md)。历史专题 PRD 仍留本目录，只更新文首交付状态；**不建 archive 子目录**。下次新需求继续在本目录加文件。

| 文档 | 状态 | 说明 |
|------|------|------|
| [里程碑需求快照 · 2026-09-20](./milestone-2026-09-20.md) | **归档快照** | 9/16–9/20 已交付 / 未做 / 下次开工约定 |
| [卖家订阅大规模采集 · 风控与运营策略](./seller-subscription-anti-risk.md) | **已部分交付** | 降速分批、多账号分工、采集调度无头模式；IP 轮换不在范围。详见里程碑。 |
| [卖家订阅采集优先级（设计 SSOT）](../design/seller-subscription-collection-strategy.md) | **现行「先采谁」** | 采集阶段与排序以设计 SSOT 为准；改逻辑先改该文再改代码 |
| [店铺数据 · 卖家订阅看板](./shop-analytics-subscription-dashboard.md) | **已交付** | `/shop-analytics` 用订阅日指标（想要/浏览），不再被空罗盘挡住 |
| [商品监控健康度与自动停用](./item-monitor-health.md) | **已交付（默认安全空跑）** | 周判定已上；默认 `MONITOR_AUTO_DISABLE_ENABLED=false`、`MONITOR_DRY_RUN=true`，不自动停用生产数据 |
| [项目健康度与缺口分析](./project-health.md) | **历史基线** | 2026-09-16 审计；文内数字已过时，以 `docs/features.md` / CI 为准 |

## 约定

- **新 PRD**：先写 `docs/prd/<主题英文短名>.md`，在本 README 登记一行，**再改代码**
- **归档快照**：阶段性交付用 `milestone-YYYY-MM-DD.md` 冻结范围；不删旧 PRD、不搬进子目录
- **与实现联动**：PRD 内「交付状态」随版本更新；细节以 `docs/features.md`、`docs/user-guide.md` 为准
- **采集顺序**：卖家订阅的阶段与优先级以 [`docs/design/seller-subscription-collection-strategy.md`](../design/seller-subscription-collection-strategy.md) 为准，PRD 不另维护第二份规则
- **计划来源**：Cursor Plan 经 PM 整理后写入本目录，不保留仅在 Plan 中的草稿

## 相关链接

- [功能文档](../features.md)
- [用户使用指南](../user-guide.md)
- [技术方案目录](../design/README.md)
- [2026-09-20 技术里程碑](../design/milestone-2026-09-20.md)
- [系统架构](../design/architecture.md)
