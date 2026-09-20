# PRD：卖家订阅大规模采集 — 风控与运营策略

> **交付状态**：**已部分交付**（2026-09-20）。未做项与本期对照见 [`milestone-2026-09-20.md`](./milestone-2026-09-20.md)  
> **创建日期**：2026-09-17  
> **范围**：卖家订阅 + 采集控制台；**IP/代理轮换明确不做**

---

## 1. 背景与问题

用户在单机上运行卖家订阅采集，监控大量卖家与商品时，担心：

1. 请求频率过高触发闲鱼风控（验证码、账号限制）
2. 除更换闲鱼账号外是否有其他手段
3. 有头浏览器长时间跑导致屏幕闪烁，影响办公

**核心判断**：闲鱼风控综合账号行为频率、设备指纹、登录态、API 模式等多维信号；**控制单号单位时间请求量**比事后换 IP 更有效。验证码类风控（`RiskControlError`）触发后，简单换号/换 IP 无法恢复，须降频并更新登录态。

---

## 2. 目标与非目标

### 2.1 目标

| ID | 目标 | 优先级 |
|----|------|--------|
| G1 | 用户可在 Web UI 配置卖家采集节奏（`pacing`）、每店上限、`Cron`，降低风控概率 | P0 |
| G2 | 用户可在采集调度中配置**无头模式**，避免 Chrome 弹窗闪烁 | P0 |
| G3 | 文档与界面明确**多账号分工**运营方式（非自动轮换） | P1 |
| G4 | 连续失败时 FailureGuard 熔断，避免失效后高频重试 | P1（已有） |

### 2.2 非目标（本期不做）

- IP / 代理池轮换（用户确认家用单 IP + 多账号分工足够）
- 卖家订阅任务内按卖家自动切换账号（`rotate` 对齐关键词任务）— 列为可选 backlog
- 有头窗口移到屏幕外（`--window-position`）— 可选体验优化

---

## 3. 用户故事

| 角色 | 故事 | 验收 |
|------|------|------|
| 运营 | 我想在采集控制台设置 Cron，在凌晨自动跑，白天不打扰 | Cron 可编辑并持久化（已有） |
| 运营 | 我想开启无头模式，保存后刷新仍生效 | 调度 `run_headless` 写入 DB 并在卡片展示 |
| 运营 | 监控 50+ 卖家时，我想分摊到多个闲鱼号 | 文档说明按卖家拆分 + `fixed` 账号 + 错峰 Cron |
| 运营 | 商品太多时我想自动放慢、分批休息 | `pacing_json` 可配置（API/DB 已有；UI 可后续增强） |
| 开发 | 旧库缺 `run_headless` 列时保存不失败 | 启动增量 DDL 自动补列 |

---

## 4. 功能需求

### 4.1 采集调度 — 无头模式（`run_headless`）

**入口**：侧边栏 **采集控制台** → **采集调度配置** → **编辑**

| 字段 | 类型 | 说明 |
|------|------|------|
| `run_headless` | boolean | `true` = 无头后台；`false` = 有头（可能闪屏） |

**优先级规则**：

1. 调度中**显式保存**的 `run_headless`（DB）
2. 未配置（`NULL`）时继承 `.env` 的 `RUN_HEADLESS`

**展示**：

- 调度卡片增加「浏览器模式」：无头（后台）/ 有头（弹窗）
- API 响应含 `run_headless_effective` 表示实际运行值

**交付状态**：✅ 已交付（2026-09-17）

- 后端：`SellerSubscriptionScheduleUpdate.run_headless`、`resolve_schedule_run_headless()`、`enrich_schedule()`
- 前端：`SellerScheduleDialog` Switch、`SellerCollectionView` 展示
- 数据库：增量 DDL + `supabase/migrations/20260917100000_seller_schedule_run_headless.sql`
- 缺陷修复：Switch `v-model:checked`；旧库缺列导致保存失败

### 4.2 节奏控制（`pacing_json`）

内置策略见 `src/domain/seller_subscription_pacing.py`：

| 参数 | 默认 | 含义 |
|------|------|------|
| `detail_delay_min/max` | 4–8s | 每条详情前等待 |
| `batch_size` | 10 | 每 N 条批休 |
| `batch_cooldown_min/max` | 60–120s | 批间休息 |
| `seller_cooldown_min/max` | 120–300s | 切换卖家前休息 |
| `long_pause_every` | 25 | 长暂停间隔 |
| `long_pause_min/max` | 90–180s | 长暂停时长 |

**推荐运营参数**（文档/运维配置，非代码默认）：

```json
{
  "item_limit": 30,
  "pacing": {
    "detail_delay_min": 6,
    "detail_delay_max": 12,
    "batch_size": 8,
    "batch_cooldown_min": 90,
    "batch_cooldown_max": 180,
    "seller_cooldown_min": 180,
    "seller_cooldown_max": 360,
    "long_pause_every": 15,
    "long_pause_min": 120,
    "long_pause_max": 240
  }
}
```

**交付状态**：✅ 能力已有；⚠️ Web UI 调度弹窗暂未暴露 `pacing` 编辑（可通过 API/DB 配置）

### 4.3 调度 — Cron 与每店上限

- **Cron**：用户自行配置，默认 `0 8 * * *`；建议凌晨或低频（每天 1–2 次）
- **`item_limit`**：默认 100，大规模场景建议 20–50

**交付状态**：✅ 已有

### 4.4 多账号分工（运营策略，非自动轮换）

当前 `launch_task_browser()` **每次任务仅使用一个账号**：

- `fixed`：指定 `account_state_file`
- `auto` / `rotate`：实际只取 `state/` 下第一个文件

**推荐做法**：

| 方式 | 做法 |
|------|------|
| 按卖家分批 + 固定账号 | 账号 A 监控卖家 1–20，账号 B 监控 21–40，各配独立 Cron |
| 错峰 | 多账号 Cron 间隔 2–4 小时 |
| 多机 | 不同机器 + 不同 `state/` 目录 |

单号建议日详情请求量 **< 300–500 次**。

**交付状态**：📖 已写入 `user-guide.md` / 本 PRD；⏳ 自动按卖家切号为 backlog

### 4.5 登录态与浏览器模式

|  topic | 说明 |
|--------|------|
| 增强快照 | Chrome 扩展导出 `cookies` + `env` + `headers` + `storage`（见 [Cookie 指南](../getting-xianyu-cookies.md)） |
| 有头 vs 无头 | 风控差别通常小于 pacing；无头优先体验，抓不到数据再切有头 |
| FailureGuard | `TASK_FAILURE_THRESHOLD=3`，暂停 86400s |

---

## 5. 风控行为（产品预期）

| 信号 | 系统行为 | 用户动作 |
|------|----------|----------|
| `baxia-dialog` / 验证 iframe | `RiskControlError`，任务终止，不轮换重试 | 停跑、降频、更新 Cookie |
| `FAIL_SYS_USER_VALIDATE` | 随机休眠后退出 | 同上 |
| 跳转登录页 | `LoginRequiredError` | 重新导入登录态 |

---

## 6. 推荐落地顺序（运营）

1. 采集控制台开启**无头模式**（若入库正常则保持）
2. 降低 `item_limit`，调慢 `pacing_json`（见 §4.2）
3. 配置 **Cron** 到凌晨或低频
4. 卖家过多时 **多账号分工** + 错峰 Cron
5. 观察日志：`baxia-dialog`、`FAIL_SYS_USER_VALIDATE`、入库 0 条

---

## 7. 交付状态总览

| 项 | 状态 |
|----|------|
| 调度 UI：`run_headless` 开关 + 展示 | ✅ 已交付 |
| DB 列 `run_headless` 增量迁移 | ✅ 已交付 |
| 默认继承 `RUN_HEADLESS` | ✅ 已交付 |
| 文档：user-guide / features | ✅ 已更新 |
| 测试：schedule 单测 + API 集成 | ✅ 已交付 |
| 调度 UI：`pacing_json` 编辑 | ⏳ Backlog |
| 卖家订阅 `rotate` 按卖家切号 | ⏳ Backlog |
| IP 代理轮换（卖家订阅） | ❌ 本期不做 |

本期（9/16–9/20）对照与 backlog 以 [`milestone-2026-09-20.md`](./milestone-2026-09-20.md) 为准。

---

## 8. 验收标准

- [x] `PATCH /api/seller-subscriptions/schedule` 可写入 `run_headless`
- [x] `GET /api/seller-subscriptions/stats` 返回持久化后的 `run_headless` / `run_headless_effective`
- [x] 采集控制台编辑弹窗可切换无头并保存；刷新后状态一致
- [x] 重启后端后旧 PostgreSQL 库自动具备 `run_headless` 列
- [ ] （运营）50 卖家场景下按本 PRD 调参后 7 日内无连续风控（需用户环境验证）

---

## 9. 相关文档与实现

- **技术方案**：[卖家订阅采集技术方案](../design/seller-subscription-scrape.md)

| 模块 | 路径 |
|------|------|
| 节奏策略 | `src/domain/seller_subscription_pacing.py` |
| 调度服务 | `src/services/seller_subscription_service.py` |
| 浏览器启动 | `src/scraper.py` → `launch_task_browser()` |
| 调度 UI | `web-ui/src/views/SellerCollectionView.vue`、`SellerScheduleDialog.vue` |
| 失败熔断 | `src/failure_guard.py` |

---

*产出：software-company 团队；Plan 迭代：2026-09-17（剔除 IP 方案、明确 Cron 用户自配、无头配置与保存缺陷修复）*
