# 闲鱼智能监控系统 — 项目健康度与缺口分析

> **文档性质**：健康度基线 PRD（software-company 团队产出）  
> **分析日期**：2026-09-16（文内「22 失败、无 pytest CI」等数字已过时）  
> **说明**：已被后续阶段覆盖，以 `docs/features.md` / CI 为准，本文件作**历史基线**。归档见 [`milestone-2026-09-20.md`](./milestone-2026-09-20.md)。
>
> **2026-09-17 更新**：阶段一–四已完成（文档对齐、pytest CI、新模块测试、前端 README + Vitest smoke）。阶段五（仓库卫生）待续。PRD 目录迁至 [`docs/prd/`](./README.md)。

---

## 1. 现状摘要

| 维度 | 状态 |
|------|------|
| 后端 | FastAPI + APScheduler + Playwright，34 个服务模块 |
| 前端 | Vue 3，**12+ 路由**（文档仍写 8 页） |
| 数据 | PostgreSQL 主存储；`jsonl/` 仅 bootstrap |
| 测试 | 164 用例；**22 失败**（约 84.6% 通过）；**无前端测试** |
| CI | 仅 Docker 构建，**无 pytest 门禁** |

### 功能 vs 文档/测试

| 模块 | 代码 | 文档 | 测试 |
|------|:----:|:----:|:----:|
| 任务监控 / AI / 通知 / 结果 | ✅ | ✅ | ✅ 较好 |
| 卖家订阅 ⭐ | ✅ | ❌ | ⚠️ 薄 |
| 店铺数据罗盘 ⭐ | ✅ | ❌ | ⚠️ API 为主 |
| Web UI 新页面 | ✅ | ❌ | ❌ 零 |

⭐ 近期新增，README 中文已写，但 `features.md` / `architecture.md` / `user-guide.md` 未更新。

---

## 2. 文档缺口

### P0

- `features.md` 缺卖家订阅、店铺罗盘、新 API（`seller_subscriptions`、`shop_analytics`）
- `architecture.md` 缺新进程链路与表模型
- `user-guide.md` 缺新功能使用说明
- `database-supabase-integration.md` 缺新表
- `README_EN.md` 严重过时（仍写 SQLite）
- `CLAUDE.md` / `AGENTS.md` 数据流描述过时

### P1

- `exploration/` 与实现文档未打通
- 无 CI/CD 说明；`web-ui/` 无 README
- `tests/README.md` 与现状严重脱节

### P2

- 无面向用户的 CHANGELOG（`log.md` 偏内部运维）
- 无贡献者 PR 检查清单（文档+测试联动）

---

## 3. 测试缺口

### 执行结果（2026-09-16）

```
164 collected → 139 passed / 22 failed / 3 skipped
```

### P0

| 问题 | 说明 |
|------|------|
| CI 无 pytest | 合并不跑测试 |
| 22 个失败用例 | results API(4)、ai_handler(6)、cli_spider(2)、failure_guard(2) 等 |
| `scheduler_service` | 零测试 |
| `scraper_shop_datacompass` | 零测试 |
| 6 个 API 零覆盖 | accounts、collections、login_state、websocket、logs、prompts |
| 前端 | 零 vitest/e2e |

### 优先修复的失败用例

1. `integration/test_api_results.py`（4）
2. `unit/test_ai_handler_analysis.py`（6）
3. `integration/test_cli_spider.py`（2）
4. `test_failure_guard.py`（2）
5. `integration/test_api_settings.py`（2）

### Windows 注意

默认 `pytest` 可能 0 collected；需 `--capture=no` 或调整 `pyproject.toml`。

---

## 4. 整理建议

| 类别 | 建议 |
|------|------|
| 文档 | 新增 `seller-subscription.md`、`shop-analytics.md`；更新 features/architecture/user-guide |
| 测试 | 补 CI pytest job；重写 `tests/README.md`；修复 22 失败用例 |
| 仓库 | `log.md` 拆为 CHANGELOG + 内部笔记；清理根目录无名文件；`data/` 保持 gitignore |
| 机制 | PR 模板增加「文档 / 测试」checkbox |

---

## 5. 建议执行顺序

### 阶段一：文档对齐（1–2 人日）

更新 features / architecture / user-guide / project-overview / database 文档；修复 README_EN。

**验收**：对照 `router/index.ts` 与 `src/api/routes/`，API/页面零遗漏。

### 阶段二：测试基线 + CI（2–3 人日）

GitHub Actions 加 pytest；修复 22 失败用例；统一集成测 fixture；更新 tests/README。

**验收**：干净环境 `pytest` green；PR 阻断失败。

### 阶段三：新模块测试补全（3–5 人日）

datacompass 解析/爬虫、卖家订阅链路、collections/accounts/logs API、scheduler 单测。

### 阶段四：前端文档 + 最小测试（2 人日）

`web-ui/README.md`；Vitest smoke；新页面截图入 user-guide。

### 阶段五：仓库卫生（1 人日）

CHANGELOG 分离；归档过时文档；CONTRIBUTING 检查项。

---

## 6. 待澄清

1. 独立 `seller_subscriptions` 表 vs `task_type=seller_subscription` 的推荐路径？
2. 店铺罗盘是否必须卖家工作台 Cookie？
3. CI 集成测：继续 InMemory 还是 ephemeral Postgres？
4. `log.md` 是否从 docs 索引剥离？

---

*产出：software-company 团队（PM 许清楚 + QA 严过关），主理人齐活林汇编*
