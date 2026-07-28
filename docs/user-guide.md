# 用户使用指南

本文档说明如何从安装到日常使用闲鱼智能监控系统。

---

## 一、项目能做什么

- 按关键词、价格、区域等条件 **自动搜索闲鱼商品**
- 用 **AI 图文分析** 或 **关键词规则** 判断是否值得购买
- 通过 ntfy / 企业微信 / Bark / Telegram 等 **推送通知**
- 在 **Web 界面** 管理任务、账号、结果和日志
- 支持 **Cron 定时** 周期性执行

---

## 二、快速开始

### 1. 安装与启动

```bash
git clone <仓库地址>
cd ai-goofish-monitor

cp .env.example .env
# 编辑 .env，配置 AI（见 docs/ai-provider.md）

chmod +x start.sh
./start.sh
```

Docker 部署：

```bash
cp .env.example .env
docker compose up -d
```

访问：**http://localhost:8000**  
默认账号：`admin` / `admin123`

### 2. 配置 AI

至少配置一种 AI 提供方，详见 [AI 提供方配置](./ai-provider.md)。

### 3. 导入闲鱼登录态

爬虫必须持有有效闲鱼 Cookie，详见 [闲鱼 Cookie 获取指南](./getting-xianyu-cookies.md)。

简要步骤：

1. Chrome 登录 [goofish.com](https://www.goofish.com)
2. 用 Chrome 扩展导出 JSON（推荐）或按 F12 手动复制 Cookie
3. Web UI → **闲鱼账号管理** → 粘贴保存

### 4. 创建并启动任务

Web UI → **任务管理** → **创建任务**：

| 模式 | 说明 |
|------|------|
| **AI 判断** | 填写详细需求，系统生成分析标准后自动图文分析 |
| **关键词判断** | 配置包含/排除关键词，命中即推荐 |

创建后点击 **启动**，或配置 Cron 定时执行。

### 5. 配置通知（可选）

在 `.env` 或 **系统设置 → 通知** 中配置至少一种渠道，例如：

```env
NTFY_TOPIC_URL=https://ntfy.sh/你的topic
```

---

## 三、Web UI 功能说明

| 页面 | 功能 |
|------|------|
| 监控概览 | 系统运行状态总览 |
| 任务管理 | 创建、编辑、启停、定时任务 |
| 闲鱼账号管理 | 导入/更新/删除登录态 |
| 结果查看 | 历史商品、筛选、价格参考 |
| 运行日志 | 每次任务执行日志 |
| 系统设置 | AI、通知、代理轮换、Prompt |

---

## 四、任务配置建议

### 新手试跑

- `max_pages = 1`
- 先不填区域筛选
- 命令行调试：`python spider_v2.py --debug-limit 3`

### AI 任务示例需求

> 监控 MacBook Air M1，8G+256G，个人自用，无维修进水，价格低于 3000。

### Cron 示例

| 表达式 | 含义 |
|--------|------|
| `0 */2 * * *` | 每 2 小时 |
| `0 9,12,18 * * *` | 每天 9、12、18 点 |

---

## 五、命令行用法

```bash
# 运行所有已启用任务
python spider_v2.py

# 指定任务
python spider_v2.py --task-name "MacBook Air M1"

# 调试模式
python spider_v2.py --debug-limit 3
```

---

## 六、目录与数据

| 路径 | 说明 |
|------|------|
| `data/app.sqlite3` | 任务、结果等主数据 |
| `state/` | 闲鱼登录态 JSON |
| `prompts/` | AI 分析 Prompt |
| `logs/` | 运行日志 |
| `images/` | 商品图片缓存 |
| `.env` | 环境配置 |

---

## 七、常见问题

| 问题 | 处理 |
|------|------|
| 前端页面空白 | 执行 `cd web-ui && npm run build` 或 `./start.sh` |
| 任务立即失败 | 检查闲鱼登录态是否过期 |
| 频繁验证码 | 降低频率；`RUN_HEADLESS=false`；使用扩展增强快照 |
| 收不到通知 | 设置里测试通知渠道；确认商品被判定为「推荐」 |
| AI 不工作 | 检查 `AI_PROVIDER` 与对应 Key/模型配置 |

---

## 八、更多文档

- [闲鱼 Cookie 获取指南](./getting-xianyu-cookies.md)
- [AI 提供方：OpenAI 与 Cursor](./ai-provider.md)
- [Chrome 扩展说明](../chrome-extension/README.md)
