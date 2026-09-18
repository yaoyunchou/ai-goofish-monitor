# Python 虚拟环境搭建报告

> 日期：2026-09-18
> 目标：为项目建立 `.venv` 虚拟环境，避免依赖污染系统 Python

## 一、完成情况

| 项目 | 状态 |
|------|------|
| `.venv` 虚拟环境 | ✅ 已创建（Python 3.12.2） |
| 依赖安装（requirements.txt） | ✅ 57 个包全部安装成功 |
| `.gitignore` 补充 venv 规则 | ✅ 已添加 `.venv/` `venv/` `env/` `.workbuddy-ai/` |
| `start.sh` 支持 venv | ✅ 已改造，自动优先使用 `.venv` |
| 空壳 `uv.lock` 清理 | ✅ 已删除（原为 4 行无效文件） |
| README / AGENTS / tests 文档更新 | ✅ 已补充虚拟环境与 pytest `-s` 说明 |
| 测试套件首次实跑 | ✅ 初测 146 passed / 14 failed / 4 skipped |
| 修复过时测试 | ✅ **全部修复，最终 160 passed / 0 failed / 4 skipped** |

## 二、环境详情

```
位置：.venv/
Python：3.12.2（系统 C:\python\python.exe）
pip：26.2.1
包数量：57
```

**核心依赖版本**：
| 包 | 版本 |
|----|------|
| fastapi | 0.141.1 |
| uvicorn | 0.53.0 |
| psycopg | 3.3.5 |
| playwright | 1.63.0 |
| openai | 3.15.0 |
| Pillow | 12.3.0 |
| pytest | 9.1.1 |
| pytest-asyncio | 1.4.0 |
| apscheduler | 3.11.3 |
| cursor-sdk | 1.0.31 |

## 三、使用方式

```bash
# 激活（Git Bash / Linux / macOS）
source .venv/Scripts/activate   # Windows
source .venv/bin/activate       # Linux / macOS

# PowerShell
.\.venv\Scripts\Activate.ps1

# 直接调用（无需激活）
./.venv/Scripts/python.exe -m pytest
./.venv/Scripts/python.exe -m src.app
```

`start.sh` 已自动适配，无需手动激活。

## 四、⚠️ 重要发现：pytest 在 Git Bash 下的坑

**现象**：直接 `pytest` 会报错并显示 `collected 0 items`：

```
ValueError: underlying buffer has been detached
```

**原因**：pytest 9.x 的输出捕获机制与 Windows Git Bash 的管道冲突，
并非代码问题。（项目 `log.md:66` 历史上测试通过时也用了 `--capture=no`，与此一致。）

**解决**：加 `-s`（等价 `--capture=no`）禁用捕获：

```bash
./.venv/Scripts/python.exe -m pytest tests/ -s
```

## 五、测试基线

**最终结果：160 passed / 0 failed / 4 skipped**（初始为 138 / 21 / 3）

### 第一轮修复（7 个）

| 测试 | 原问题 | 修复方式 |
|------|--------|---------|
| `test_ai_handler_analysis.py`（6 个） | mock 已废弃的 `ai_handler.client` 模块级 OpenAI client | 重写为 mock `AIClient` 实例的 `_call_ai()`；移除已下移到 AIClient 层的重复断言。**由 6 个用例扩充为 7 个**（新增客户端不可用、prompt 缺失、非法 JSON 重试恢复等） |
| `test_ai_client.py::test_sanitize_no_proxy_handles_both_keys` | Windows 环境变量大小写不敏感，`NO_PROXY` 与 `no_proxy` 实为同一变量，断言必然失败 | 加 `skipif(os.name == "nt")`，并新增 Windows 专用用例 `test_sanitize_no_proxy_handles_single_key_on_windows` |

**重要发现**：AI 兼容性降级逻辑（结构化输出 / temperature / API 回退）已从 `ai_handler`
**下移到 `AIClient._call_ai`**，并在 `tests/unit/test_ai_client.py` 中被完整覆盖
（`test_call_ai_retries_without_structured_output_when_model_rejects_it` 等）。
原 `test_ai_handler_analysis.py` 里的同类断言属于**架构迁移后的残留**，已清理。

### 第二轮修复（剩余全部）

初测的 14 个失败按**实测根因**分为 5 类（注意：早期分类中把 `test_failure_guard`
误判为数据库问题，实测证明是 Windows 平台问题，此处已纠正）：

| 类别 | 数量 | 真实根因 | 修复方式 |
|------|------|---------|---------|
| DB 隔离缺失 | 7 | `get_postgres_dsn()` 拿不到 `DATABASE_URL`（4 个直接抛错，3 个表现为 API 500） | 新增 `tests/fakes/sqlite_connection.py` + `sqlite_row.py`：基于**真实 SQLite 内存库**的离线替身，复刻 `DbConnection` 接口与 psycopg `dict_row` 语义，使存储层的 Postgres 方言 SQL 能被真实校验 |
| Windows 平台差异 | 2 | `_FileLock` 锁定目标文件 → 后续 `os.replace` 原子替换失败（`WinError 5`） | **源码修复** `src/failure_guard.py`：锁改由独立 `.lock` 文件承载，目标文件不再被持有；并加 `msvcrt` 支持实现跨平台 |
| 接口未同步 | 2 | 测试用 `types.ModuleType` 伪造 `src.scraper` 时漏挂 `launch_task_browser` | 补齐 fake 模块导出符号 |
| 断言过时（SKU） | 1 | `parse_title_sku_fragments` 只识别英文逗号，无法切分顿号分隔的规格 | **源码修复** `src/item_detail_parser.py`：分隔符正则改为 `[、,，]`，并用 `rsplit(maxsplit=1)` 剥离混入的标题正文 |
| 构建配置矛盾 | 1 | 测试断言 `.dockerignore` 不含 `web-ui/dist`，但它确实包含 | 从 `.dockerignore` 移除 `web-ui/dist`（多阶段构建需要该目录参与复制），保留 `dist/` |
| 其他 | 1 | `test_app_lifespan` 的 DB 依赖 | 同「DB 隔离缺失」，接入同一替身方案 |

### 新增测试基础设施

| 文件 | 用途 |
|------|------|
| `tests/fakes/sqlite_connection.py` | 进程内 SQLite 内存库替身，提供与 `DbConnection` 一致的 `execute`/`commit`/`raw` 接口 |
| `tests/fakes/sqlite_row.py` | 复刻 psycopg `dict_row` 的按列名访问语义 |

> 该替身**不是 SQL 解析 mock**：所有断言都建立在真实执行的 SQL 之上，
> 存储层刻意编写的 Postgres 方言（`ON CONFLICT`、`RETURNING`、`DISTINCT ON`、
> `CREATE INDEX IF NOT EXISTS`、`IS TRUE`、`CAST(x AS ...)`）均能被真实校验。
> docstring 中已诚实标注替身边界（不强制外键、JSON 存 TEXT 等）。

## 六、遗留事项

1. **`.workbuddy-ai/` 已加入 `.gitignore`** — 工作区元数据，不应进版本库
2. **4 个 skipped** — 均为 Live smoke 测试（需真实凭据/外部服务），默认关闭，属预期行为
3. **pytest 必须加 `-s`** — Windows Git Bash 下的已知限制，已在 `tests/README.md` 记录

> 注：项目 `pyproject.toml` 的 `[tool.pytest.ini_options]` 未配置 `-s`，
> 建议在团队内统一约定或在 `addopts` 中补充，避免每次踩坑。
