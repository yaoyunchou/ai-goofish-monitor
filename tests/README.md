# 测试指南

本项目使用 **pytest**。完整功能说明见 [docs/features.md §13](../docs/features.md#十三测试体系)。

## 概览（2026-09-17，阶段四完成）

| 指标 | 数量 |
|------|------|
| 可收集用例 | **186**（含 3 个 live，默认 skip） |
| 离线基线 | **183 passed, 3 skipped** |
| 单元测试 | `tests/unit/`（约 43 个文件） |
| 集成测试 | `tests/integration/`（11 个文件） |
| Live 冒烟 | `tests/live/`（需 `RUN_LIVE_TESTS=1`） |
| 前端单测 | `web-ui/` Vitest smoke（**9** 用例，`npm test`） |

## 环境准备

```bash
pip install -r requirements.txt
```

## 运行命令

```bash
# 推荐：全量离线测试
python -m pytest -q

# 覆盖率
python -m pytest --cov=src

# 单文件 / 单函数
python -m pytest tests/integration/test_api_tasks.py
python -m pytest tests/unit/test_utils.py::test_safe_get_nested_and_default
```

### Windows 注意

若出现 `collected 0 items` 或 capture 相关错误，使用：

```bash
python -m pytest -q --capture=no
```

`pyproject.toml` 已默认 `--capture=no`。第三方插件冲突时可设：

```bash
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD="1"
python -m pytest -q
```

### CI

| 工作流 | 内容 |
|--------|------|
| `.github/workflows/pytest.yml` | 后端 pytest（push/PR） |
| `.github/workflows/web-ui.yml` | 前端 Vitest + `npm run build`（`web-ui/` 变更时） |

前端本地测试：`cd web-ui && npm test`。详见 [web-ui/README.md](../web-ui/README.md)。

## 目录结构

```
tests/
├── conftest.py              # 共享 fixtures（API Client、内存仓储、样例任务）
├── fixtures/                # 搜索/用户/评价/任务配置/店铺罗盘 datacompass 样例 JSON
├── fakes/
│   └── memory_task_repository.py
├── unit/                    # 单元测试（AI、解析、关键词、卖家订阅、店铺罗盘等）
├── integration/             # API / CLI / 解析管道集成测试
├── live/                    # 真实流量冒烟（默认 skip）
├── test_failure_guard.py
└── test_frontend_build_paths.py
```

### 集成测试覆盖的 API

| 文件 | 模块 |
|------|------|
| `test_api_tasks.py` | `/api/tasks` |
| `test_api_results.py` | `/api/results` |
| `test_api_settings.py` | `/api/settings` |
| `test_api_dashboard.py` | `/api/dashboard` |
| `test_api_seller_subscriptions.py` | `/api/seller-subscriptions` |
| `test_api_shop_analytics.py` | `/api/shop-analytics`（dashboard + 旧 overview） |
| `test_api_accounts.py` | `/api/accounts` |
| `test_api_collections.py` | `/api/collections` |
| `test_api_logs.py` | `/api/logs` |
| `test_cli_spider.py` | `spider_v2.py` |
| `test_pipeline_parse.py` | `parsers.py` |

### 阶段三新增单测

| 文件 | 覆盖 |
|------|------|
| `test_scheduler_service.py` | `reload_seller_subscription_job` 等调度逻辑 |
| `test_scraper_shop_datacompass.py` | 店铺罗盘 datacompass fixture 解析与 persist |
| `test_seller_subscription_scraper.py` | 卖家订阅入库过滤（想要+浏览量）、空配置跳过 |
| `test_seller_item_daily_storage.py` | 日级 UPSERT（同日覆盖 raw）、Asia/Shanghai snapshot_day |
| `test_shop_analytics_dashboard.py` | 订阅看板口径：空心日 null、7d 不跨日求和、SQL GROUP BY |

**尚未覆盖的 API**：`prompts`、`login_state`、`websocket`。

## 隔离设计

- 测试使用 `data/.pytest-env`，不读取仓库根目录 `.env`
- API 集成测默认 `InMemoryTaskRepository`（任务 CRUD）
- 部分结果/卖家订阅测试使用 PostgreSQL fixture 或 mock 存储
- Live 测试在临时目录运行，清空通知环境变量
- `test_cli_spider.py` 会临时 `pop` `src.seller_subscription_scraper`；依赖该模块的用例应在函数内 `importlib.import_module` 重新加载（见 `test_seller_subscription_scraper.py`）

## Live Smoke

```bash
# 一键脚本（推荐）
./run_live_smoke.sh

# 手动
RUN_LIVE_TESTS=1 \
LIVE_TEST_ACCOUNT_STATE_FILE=/absolute/path/to/account.json \
LIVE_TEST_KEYWORD="MacBook Pro M2" \
pytest tests/live -m live -v
```

可选变量：`LIVE_TEST_TASK_NAME`、`LIVE_EXPECT_MIN_ITEMS`、`LIVE_TEST_DEBUG_LIMIT`、`LIVE_TIMEOUT_SECONDS`。

## 编写规范

1. 新文件放在 `tests/unit/` 或 `tests/integration/`
2. 文件名 `test_*.py`，函数名 `test_*`
3. 同步测试，不依赖 `pytest-asyncio`
4. 外部依赖（Playwright / AI / 通知 / 网络）统一 mock
5. 样例数据放 `tests/fixtures/`
6. **新 API 路由应补集成测试**；新 service 优先单测

## PR 检查清单

- [ ] `python -m pytest -q` 全绿
- [ ] 新功能已补测试或说明为何不测
- [ ] 文档已同步（`docs/features.md` / `user-guide.md` 等）
