# 交付报告：需求与技术方案归档 · 2026-09-20

> software-company 部分工作流（文档归档）：PM [许清楚](8fe7356e-681f-438e-8c91-c9acba642d61) + 架构师 [高见远](d029b148-e9cd-4734-baa0-e6175fc100a9) → 主理人落盘。  
> **不改业务代码、不起服务。**

## 做了什么

用户确认本期需求基本完成、暂无新想法，将 2026-09-16～09-20 的产品与技术文档整理成可对照的冻结快照，方便下次从干净索引继续开发。

| 产物 | 路径 |
|------|------|
| 需求里程碑 | `docs/prd/milestone-2026-09-20.md` |
| 技术里程碑 | `docs/design/milestone-2026-09-20.md` |
| PRD 索引 | `docs/prd/README.md`、`docs/prd.md`、`docs/README.md` |
| 设计索引 | `docs/design/README.md`、`docs/design.md` |
| 全量架构指针 | `docs/design/architecture.md` 文首 |

历史专题 PRD / 设计文**仍留原目录**，只更新文首交付状态；**不建 archive 子目录**。

## 已交付 vs 未做（摘要）

**已交付**：三阶段采集优先级、订阅日指标看板、采集控制台（无头/Cron/下次执行/日志）、调度不被 `reload_jobs` 卸掉、删除订阅级联、商品周健康度（默认 dry-run）。

**未做 / 非目标**：IP 轮换、datacompass 进主看板、选品预算接入 scraper、健康度默认真正 mute、错过 Cron 自动补跑。

## 下次开工

1. 新需求先写 `docs/prd/<英文短名>.md` 并登记 README，再改代码。  
2. 采集顺序仍以 `docs/design/seller-subscription-collection-strategy.md` 为 SSOT。  
3. 改哪里看技术里程碑 §6 / §7。

## 验证

文档交叉链接与索引登记（静态阅读）。未跑 pytest / 未起服务。
