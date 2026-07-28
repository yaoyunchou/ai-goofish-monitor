# AI 提供方配置：OpenAI 兼容接口 与 Cursor SDK

本项目支持两种 AI 调用方式，通过 `AI_PROVIDER` 环境变量切换。商品分析（图文）与 AI 任务标准生成均走同一套抽象层。

---

## 总览对比

| 项目 | OpenAI 兼容（默认） | Cursor SDK |
|------|---------------------|------------|
| 环境变量 | `AI_PROVIDER=openai` | `AI_PROVIDER=cursor` |
| 典型配置 | `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL_NAME` | `CURSOR_API_KEY` / `CURSOR_MODEL_NAME` |
| 调用方式 | OpenAI Chat Completions / Responses API | Cursor `AsyncAgent.prompt()` |
| 多模态 | 依赖所选模型是否支持 Vision | 支持文本 + 图片（`SDKImage`） |
| 适用场景 | 通用大模型网关（OpenAI、ModelScope、DeepSeek 等） | 已订阅 Cursor、希望用 Cursor 模型与 Agent 运行时 |
| 默认 | ✅ 是 | 否，需显式切换 |

---

## 方式一：OpenAI 兼容接口（默认）

适用于任何提供 **OpenAI 兼容 HTTP API** 的服务商。

### `.env` 配置示例

```env
AI_PROVIDER=openai

OPENAI_API_KEY=sk-你的key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL_NAME=gpt-4o

# 可选
PROXY_URL=
ENABLE_RESPONSE_FORMAT=true
ENABLE_THINKING=false
AI_DEBUG_MODE=false
```

### 要求

- `OPENAI_MODEL_NAME` 必须支持 **图片输入**（多模态），否则商品图片分析无效
- 部分模型不支持 `response_format=json_object`，项目会自动降级重试

### Web UI 配置

**系统设置 → AI** → 选择 **OpenAI Compatible**，填写 Base URL、API Key、模型名。

---

## 方式二：Cursor SDK

适用于希望使用 **Cursor 官方 Python SDK**（`cursor-sdk`）调用 Cursor 模型的场景。

### `.env` 配置示例

```env
AI_PROVIDER=cursor

# 在 https://cursor.com/dashboard/api 创建 API Key
CURSOR_API_KEY=crsr_你的key

# 模型 ID，例如 composer-2.5
CURSOR_MODEL_NAME=composer-2.5

# 运行环境：local | cloud
CURSOR_RUNTIME=local

# local 模式工作目录（默认项目根目录）
CURSOR_LOCAL_CWD=.

# cloud 模式可选：逗号分隔的 GitHub 仓库 URL
CURSOR_CLOUD_REPOS=
```

### 运行模式说明

| 模式 | 配置值 | 说明 |
|------|--------|------|
| **local** | `CURSOR_RUNTIME=local` | 使用本机 Cursor 运行时；需安装 Cursor IDE/CLI，适合本地开发 |
| **cloud** | `CURSOR_RUNTIME=cloud` | 使用 Cursor Cloud Agent；适合无本地 Cursor 环境的服务器/Docker |

### Web UI 配置

**系统设置 → AI** → 选择 **Cursor SDK**，填写 API Key、模型、Runtime 等，点击 **测试连接** 验证。

### 获取 Cursor API Key

1. 打开 [Cursor Dashboard → API Keys](https://cursor.com/dashboard/api)
2. 创建 User API Key 或 Service Account Key
3. 写入 `.env` 的 `CURSOR_API_KEY` 或在 Web UI 中保存

### 注意事项

- Cursor SDK 按 Cursor 的 token 计费，与 OpenAI 直连计费方式不同
- `local` 模式在 **Docker 容器内通常不可用**，容器部署请优先考虑 `cloud`
- `cloud` 模式如需关联代码仓库，可配置 `CURSOR_CLOUD_REPOS`

---

## 从 OpenAI 切换到 Cursor（迁移步骤）

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

确认已安装 `cursor-sdk`：

```bash
pip show cursor-sdk
```

### 2. 修改 `.env`

```env
# 注释或保留原 OpenAI 配置（切换后不再使用，但可留作备份）
# OPENAI_API_KEY=...
# OPENAI_BASE_URL=...
# OPENAI_MODEL_NAME=...

AI_PROVIDER=cursor
CURSOR_API_KEY=crsr_xxx
CURSOR_MODEL_NAME=composer-2.5
CURSOR_RUNTIME=local
```

### 3. 重启服务

```bash
# 本地
python3 -m src.app

# 或
./start.sh

# Docker
docker compose restart app
```

### 4. 验证

1. Web UI → **系统设置 → AI** → **测试连接**
2. 创建一个小任务，`--debug-limit 3` 试跑：

```bash
python spider_v2.py --task-name "你的任务名" --debug-limit 3
```

3. 查看 `logs/` 中是否有 AI 分析成功记录

### 5. 回退到 OpenAI

```env
AI_PROVIDER=openai
```

重启服务即可，无需改代码。

---

## 技术实现说明（开发者向）

### 架构

```text
商品分析 / 任务标准生成
        ↓
   AIClient (src/infrastructure/external/ai_client.py)
        ↓
   ┌────────────────┬─────────────────────┐
   │ openai         │ cursor              │
   │ AsyncOpenAI    │ CursorAITransport   │
   │ chat/responses │ AsyncAgent.prompt() │
   └────────────────┴─────────────────────┘
```

### 关键文件

| 文件 | 作用 |
|------|------|
| `src/infrastructure/config/settings.py` | `AISettings`，读取 `AI_PROVIDER` 等环境变量 |
| `src/infrastructure/external/ai_client.py` | 统一入口，按 provider 路由 |
| `src/infrastructure/external/cursor_transport.py` | Cursor SDK 封装，支持文本 + 图片 |
| `src/ai_handler.py` | 爬虫侧商品 AI 分析 |
| `src/prompt_utils.py` | AI 任务标准生成 |
| `src/api/routes/settings.py` | Web UI 设置与测试接口 |
| `web-ui/src/views/SettingsView.vue` | 前端 AI 配置面板 |

### Cursor 调用流程

1. 将商品 JSON + Prompt 与图片路径组装为消息
2. `CursorAITransport.complete()` 提取文本与图片
3. 图片转为 `SDKImage`（支持本地文件、Data URL、HTTP URL）
4. 调用 `AsyncAgent.prompt(UserMessage(...), AgentOptions(...))`
5. 解析返回的 JSON，得到 `is_recommended`、`reason` 等字段

### OpenAI 调用流程（保持不变）

1. `AIClient._call_ai()` 构建 Chat Completions / Responses 请求
2. 自动处理 JSON 输出、temperature、API 模式回退等兼容性
3. 解析响应 JSON

### 相关测试

```bash
pytest tests/unit/test_cursor_transport.py
pytest tests/unit/test_ai_client.py
pytest tests/integration/test_api_settings.py
```

---

## 常见问题

### Q: 设置了 Cursor 但还是走 OpenAI？

检查 `.env` 中 `AI_PROVIDER=cursor` 是否拼写正确，修改后需 **重启后端**。Web UI 保存的设置会写入 `.env`。

### Q: Cursor 测试连接失败（local）？

- 确认本机已安装并登录 Cursor
- 确认 `CURSOR_API_KEY` 有效
- Docker 环境请改用 `CURSOR_RUNTIME=cloud`

### Q: 两种模式可以同时用吗？

不可以。同一时刻只有一个 `AI_PROVIDER` 生效。可按需切换并重启服务。

### Q: 关键词判断模式需要 AI 吗？

不需要。`decision_mode=keyword` 的任务不调用 AI，但 **AI 任务创建**（生成分析标准）仍需要配置好的 AI 提供方。
