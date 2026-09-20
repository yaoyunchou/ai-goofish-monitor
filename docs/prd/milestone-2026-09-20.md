# 里程碑需求快照 · 2026-09-20

> **文档性质**：本期已交付范围的归档快照（software-company / PM 许清楚）  
> **项目**：`ai-goofish-monitor`（FastAPI + Vue 3 + PostgreSQL）  
> **周期**：约 2026-09-16 ～ 2026-09-20  
> **语言**：中文  
> **用途**：冻结「这期做完了什么 / 明确没做什么 / 下次怎么开新需求」。不替代各专题 PRD 全文。  
> **技术对照**：[`docs/design/milestone-2026-09-20.md`](../design/milestone-2026-09-20.md)

---

## 1. 归档说明

用户确认本期需求基本完成、暂无新想法，故做一次**需求侧归档**。

| 约定 | 说明 |
|------|------|
| 冻结范围 | 本文锁定 9/16–9/20 用户侧已完成的产品能力；之后新想法另开新 PRD，不回改本文「已交付」表充当期中需求。 |
| 不删历史 | 专题 PRD 仍留在 `docs/prd/`，只补「交付状态」。不建 `docs/prd/archive/`，下次新文件继续放本目录。 |
| 不写实现 | 本文只写产品能力与验收意图。采集「先采谁」的规则以设计 SSOT 为准，此处不重复。 |
| 技术文档 | 实现与模块边界见技术里程碑与 `docs/design/`；细节以 `docs/features.md`、`docs/user-guide.md` 为准。 |

**一句话复述本期**：卖家订阅能按约定顺序采、控制台能定时无头跑、店铺分析能看见想要/浏览、删订阅不留脏店、商品健康度能周判定但默认不动生产数据。选品「保量+补位」只有设计与只读模拟，**不算已交付**。

---

## 2. 已交付能力（用户侧）

| # | 能力（产品语言） | 用户能做什么 | 需求/策略出处 |
|---|------------------|--------------|----------------|
| 1 | 卖家订阅三阶段采集优先级 | 一轮任务里先对齐全部已订阅店的在售列表，再补「今日还没采到的」，最后才刷新已有日指标；**新店优先**。 | 策略 SSOT：[`docs/design/seller-subscription-collection-strategy.md`](../design/seller-subscription-collection-strategy.md)。产品背景：[`seller-subscription-anti-risk.md`](./seller-subscription-anti-risk.md)。**PRD 不另写第二套顺序。** |
| 2 | 店铺分析页改订阅看板 | 打开 `/shop-analytics`（侧栏「店铺数据」）即可看订阅日指标（想要 / 浏览、店排行、近 7 日趋势）；**不再被空罗盘挡住**。 | [`shop-analytics-subscription-dashboard.md`](./shop-analytics-subscription-dashboard.md) |
| 3 | 采集控制台可运营 | 可配**无头**、**Cron**、看到**下次执行**；可开关**实时日志**；一轮里被整店跳过时有**汇总**可看。 | [`seller-subscription-anti-risk.md`](./seller-subscription-anti-risk.md) |
| 4 | 订阅定时不被「重载任务」拆掉 | 重载关键词/普通任务的定时作业时，**不会卸掉**卖家订阅 Cron。每天 **01:00** 要跑起来，**后端进程必须在跑**（进程没了就不会到点执行）。 | 与 #3 同一产品线；错过点不补跑见下文 backlog |
| 5 | 删除订阅不留残店 | 删除某店订阅后，该店商品与日指标一并清掉；订阅列表和店铺分析看板**只展示仍在订阅的店**。 | 看板口径见 [`shop-analytics-subscription-dashboard.md`](./shop-analytics-subscription-dashboard.md) |
| 6 | 商品周健康度（默认空跑） | 按自然周看浏览/想要，挑出「两边都低且不增长」的商品。默认 **`MONITOR_AUTO_DISABLE_ENABLED=false`**、**`MONITOR_DRY_RUN=true`**：判定可落库观察，**不自动停用生产监控**。 | [`item-monitor-health.md`](./item-monitor-health.md) |

---

## 3. 明确未做 / Backlog

下列**不要**当成已上线能力。有新想法时各自开新 PRD（或在原 PRD 改状态后再开发）。

| 项 | 状态 | 说明 |
|----|------|------|
| IP / 代理轮换 | **非目标** | [`seller-subscription-anti-risk.md`](./seller-subscription-anti-risk.md) 已确认不做；家用单 IP + 降速 + 多账号分工。 |
| 工作台 datacompass 揉进主看板 | **P2 未做** | `/shop-analytics` 主数据是订阅日指标；罗盘/曝光/支付等不进主看板。 |
| 选品预算「保量 + 补位」接入采集 | **未交付** | 仅有设计定稿 + **只读模拟脚本**，**未接入采集主路径**。设计可开工：[`docs/design/item-selection-budget.md`](../design/item-selection-budget.md)。 |
| 健康度默认真正自动停用 | **未做（有意）** | 能力已在，默认空跑。要自动停用须**用户自己改 env**，并先按健康度 PRD 体检校准。 |
| 错过的 Cron 自动补跑 | **未做** | 到点时进程没在跑 = 该次跳过，系统不会醒来后补跑。 |

**不属于「已交付」的同期产物**：选品预算算法（设计 + 模拟）——有文档、无产品闭环。

---

## 4. 下次新需求怎么开

从干净目录继续，不要在本快照上叠期中需求。

1. **先写 PRD**：`docs/prd/<英文短名>.md`（做什么、为什么、验收；中文）。
2. **登记索引**：在 [`docs/prd/README.md`](./README.md) 加一行；兼容入口 [`docs/prd.md`](../prd.md) 可补链接。
3. **再改代码**：无新 PRD、未登记，不进入实现。
4. **采集顺序**：卖家订阅「采谁、先采什么、分几段」仍以  
   [`docs/design/seller-subscription-collection-strategy.md`](../design/seller-subscription-collection-strategy.md)  
   为 **SSOT**。要改顺序：先改该设计文，再改代码；PRD 只写目标与验收，不另维护第二份规则。
5. **本快照**：只作 2026-09-20 对照；新交付记在新 PRD 的「交付状态」，必要时再开下一份 `milestone-YYYY-MM-DD.md`。

### 建议下一张可开工的票（非承诺）

- 选品预算接入采集主路径（设计已定稿，缺产品验收 PRD 与实现）。
- 健康度：观察空跑若干周后，由用户决定是否改 env 真正停用。
- datacompass 进看板：仅当用户明确要工作台指标时再开 P2 PRD。
