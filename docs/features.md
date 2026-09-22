# 功能文档（Features）

> 本文档系统性地罗列 `ai-goofish-monitor` 的**全部功能点**：Web UI 功能、后端 API 端点、任务配置字段、AI 能力、通知渠道、账号/代理轮换、价格洞察、黑名单、命令行、Chrome 扩展、测试体系。
>
> 适用于：功能验收、测试设计、二次开发、使用者查阅。
>
> **2026-09-20 归档**：本期需求/设计快照见 [`docs/prd/milestone-2026-09-20.md`](./prd/milestone-2026-09-20.md) 与 [`docs/design/milestone-2026-09-20.md`](./design/milestone-2026-09-20.md)。本文仍是已实现功能清单。

---

## 目录

1. [功能总览](#一功能总览)
2. [Web UI 功能](#二web-ui-功能)
3. [后端 API 端点清单](#三后端-api-端点清单)
4. [任务配置字段详解](#四任务配置字段详解)
5. [AI 能力](#五ai-能力)
6. [通知渠道](#六通知渠道)
7. [账号与代理轮换](#七账号与代理轮换)
8. [结果管理：筛选/洞察/黑名单/导出](#八结果管理)
9. [商品收录与 SKU](#九商品收录与-sku)
10. [命令行功能](#十命令行功能)
11. [Chrome 扩展功能](#十一chrome-扩展功能)
12. [配置项完整清单](#十二配置项完整清单)
13. [测试体系](#十三测试体系)
14. [错误码与诊断](#十四错误码与诊断)

---

## 一、功能总览

| 模块 | 主要功能点 |
|------|-----------|
| 任务管理 | AI/关键词双模式创建、编辑、启停、删除、Cron 定时、账号绑定、区域三级筛选 |
| 爬虫抓取 | 搜索、新发布/个人/包邮/区域/价格筛选、分页、详情、卖家画像、反检测、风控处理 |
| AI 分析 | 多模态图文分析、AI 品类过滤、AI 生成分析标准、响应校验与降级重试 |
| 关键词判定 | 关键词规则（OR）、ASCII 词边界匹配 |
| 通知推送 | 6 渠道并发、模板变量、测试通知 |
| 结果管理 | 分页/筛选/排序、价格洞察、黑名单、收藏、CSV/NDJSON 导出 |
| 账号体系 | 登录态导入/更新/删除、策略 auto/fixed/rotate、代理池轮换 |
| 稳定性 | 失败熔断、自动恢复、任务日志清理 |
| 运维 | Docker 多架构部署、CI 自动发镜像、健康检查、数据库自检 |
| 卖家订阅 | 独立 CRUD + 全局 Cron；C 端主页采集；仅入库同时有「想要+浏览量」的商品 |
| 店铺分析 | 订阅日指标看板（今天/近7天）：想要/浏览、店排行、热门商品；旧 datacompass 接口保留但不作主页面数据源 |
| 小红书监控 | 公开商品累计已售；今日/昨日/上小时高水位差；不使用小红书登录 |

---

## 二、Web UI 功能

### 2.1 监控概览（DashboardView，`/dashboard`）

- **4 个统计卡片**：活跃任务数、已扫描商品数、推荐商品数（AI 推荐 + 关键词推荐拆开）、监控任务总数
- **重点任务面板**：
  - 当前关注任务名称/关键词/商品总数 + 最近更新时间
  - 价格洞察卡片：当前均价、历史均价、当前最低价
  - 价格趋势图（纯 SVG：均价实线 + 中位数虚线 + 渐变面积）
  - 补充指标：当前中位数、历史最低价、历史最高价
- **活动流**：最近 8 条活动（任务状态/推荐/扫描），点击跳转对应页面
- **AI 智能建议**：根据任务状态生成优化建议，点击可直接跳转任务编辑页并预填
- **创建任务快捷入口**

### 2.2 任务管理（TasksView，`/tasks`）

- **任务列表**（桌面端表格 / 移动端卡片双模式）：
  - 启用/禁用开关（乐观更新）
  - 运行状态指示灯（ACTIVE/IDLE）
  - 任务名称 + AI/KEYWORD 模式徽章
  - 关键词 + 描述摘要 + 账号策略与账号名
  - 价格区间、个人卖家/包邮/地区筛选标签
  - AI 模式：提示词文件 + 「刷新标准」按钮（重新生成 AI 判定标准）
  - 关键词模式：关键词规则数量
  - Cron 表达式 + 下次运行倒计时（每秒刷新）+ 页数
  - 操作：启动 / 停止 / 编辑 / 删除（均带确认）
- **创建/编辑任务对话框**：复用 `TaskForm`，支持 URL 参数 `?create=1`、`?edit={id}` 直达
- **刷新标准对话框**：输入描述，AI 重新生成分析标准

### 2.3 闲鱼账号管理（AccountsView，`/accounts`）

- Cookie 获取指南卡片（5 步教程）
- 账号列表：名称、文件路径、操作（创建任务/更新/删除）
- 创建/更新账号对话框（名称 + JSON 内容，需合法 JSON）
- 账号名规则：`^[a-zA-Z0-9_-]{1,50}$`

### 2.4 结果浏览（ResultsView，`/results`）

- **筛选栏**：结果文件下拉（按任务名显示）、排序字段（爬取/发布/价格/命中数）、升降序、筛选复选框（仅 AI 推荐 / 仅关键词推荐 / 包含隐藏；AI 与关键词互斥）
- **操作**：刷新、管理黑名单、导出 CSV、删除结果文件
- **洞察面板**：Market Intelligence（当前均价/历史均价/当前最低价）、价格趋势曲线、趋势解读卡片、快照说明（最新快照时间/中位数/历史极值）
- **结果网格**（1/2/3/4 列响应式）：
  - 商品卡片：图片（悬停放大）、标题、当前价/原价
  - AI 状态：强烈推荐/不推荐/分析中 + 匹配度百分比 + 进度条 + 理由（可展开）
  - 价格洞察：市场均价、历史最低价
  - 卖家昵称、爬取时间
  - 操作：收藏（跳转收藏详情）、屏蔽/取消屏蔽、打开闲鱼链接
  - 已隐藏商品：半透明 + 隐藏原因覆盖层（黑名单/过期/手动），规则隐藏不可取消

### 2.5 收藏详情（CollectionDetailView，`/results/collected/:id`）

- 收藏商品标题 + SKU 获取状态 + 错误提示
- SKU 表格（规格/价格/SKU ID）
- 刷新 SKU 按钮；状态为 pending/running 时每 2.5s 自动轮询，完成/失败停止
- 打开闲鱼链接

### 2.6 运行日志（LogsView，`/logs`）

- 任务选择下拉（自动选中运行中的任务）
- 深色日志区、等宽字体、自动换行
- 自动刷新开关（默认开，2s 轮询）、自动滚动开关
- 手动刷新、清空日志（带确认）
- 向上分页加载历史日志（保持滚动位置）
- 日志防膨胀：超 20 万字符截取后 15 万 + 提示；支持日志轮转检测重连

### 2.7 系统设置（SettingsView，`/settings`，5 个 Tab）

| Tab | 功能 |
|-----|------|
| **AI** | Provider 选择（OpenAI/Cursor）、各 Provider 参数、测试连接、保存 |
| **轮换** | 账号轮换（启用/目录/模式/重试/黑名单 TTL）+ 代理轮换（启用/模式/池/重试/黑名单 TTL） |
| **通知** | PC 转移动开关 + 6 渠道独立配置/测试/清除；敏感字段不回显（`*_SET` 标志）；Webhook 模板变量；全局测试/保存 |
| **系统状态** | 爬虫进程状态、env 文件状态、AI 配置状态、已配置渠道列表、运行时详情（数据库/AI Provider/端口/Cursor Agent）、完整环境变量表（脱敏）、.env 路径、刷新 |
| **提示词** | 提示词文件下拉（记忆选择）+ 内容编辑器 + 保存 |

### 2.8 登录（LoginView，`/login`）

- 账号密码登录（默认 `admin/admin123`）
- 语言切换、错误提示（缺凭证/凭证错误）
- 登录成功跳回 `redirect` 参数路径

### 2.9 全局能力

- **中英文国际化**（vue-i18n，默认中文，可切换）
- **WebSocket 实时刷新**：任务状态、结果、仪表盘数据变化即时更新
- **移动端适配**：侧边抽屉导航、卡片式列表
- **主题**：Tailwind CSS 变量驱动，亮/暗模式

### 2.10 卖家订阅（SellerSubscriptionView 等）

| 路由 | 页面 | 功能 |
|------|------|------|
| `/seller-subscriptions/sellers` | 卖家列表 | 订阅 CRUD、启用/禁用、全局 Cron 配置、手动触发采集 |
| `/seller-subscriptions/sellers/:sellerUserId` | 卖家详情 | 画像快照、在售商品概览 |
| `/seller-subscriptions/items` | 商品列表 | 分页/搜索/排序（想要数、浏览量、价格、快照时间） |
| `/seller-subscriptions/items/:itemId` | 商品详情 | 指标趋势、详情 API 快照、「查看原页面」跳转闲鱼 |
| `/seller-subscriptions/collection` | 采集控制台 | 采集进度与统计；调度配置含 Cron、每店上限、**无头模式**（`run_headless`） |

**推荐路径**：使用独立 `seller_subscriptions` 表 + `/api/seller-subscriptions`（与任务管理的 `task_type=seller_subscription` 解耦）。采集入口：`POST /api/seller-subscriptions/run` 或 Cron 调度。

**入库规则**：仅当商品同时具有「想要人数」和「浏览量」时写入日级表：`seller_subscription_items`（静态）+ `seller_item_daily_metrics`（want/view，每日一条）+ `crawl_raw_records`（原始 JSON，与日指标 1:1）。同日再次采集覆盖，不新增行。

### 2.11 店铺分析（ShopAnalyticsView，`/shop-analytics`）

侧栏仍叫「店铺数据」。页内标题为 **店铺分析**，主数据源是卖家订阅日指标（`seller_item_daily_metrics`），不是工作台 datacompass。

- 周期：默认 **今天**（Asia/Shanghai），可切换 **近 7 天**
- 概览卡片：订阅店数（仅 enabled）、已采商品去重、想要合计、浏览合计。近 7 天的想要/浏览取区间内最新有数据日，**不跨日相加**
- 趋势图：始终近 7 个上海日历日；无数据日空心（JSON `null`，不补 0）
- 店铺排行（默认浏览降序，表头可改排序）→ 卖家详情；热门商品 Top 10 → 商品详情
- 刷新只重新 `GET /api/shop-analytics/dashboard`；本页不触发采集
- 无日指标时引导去 **采集控制台** `/seller-subscriptions/collection`（次链卖家列表）

**口径**：监控商品 = 指定日（或区间）日指标去重 `item_id`，不是画像 `item_count`，也不是全库跨日去重。旧 `GET /overview` 等 datacompass 接口仍保留给首页/兼容，主页面不再调用。

### 2.12 小红书监控（XhsBoardView，`/xhs`）

独立侧栏分组。只采集公开商品页，不使用小红书登录态。

- 「添加商品」页 `/xhs/add`：每行一个公开链接或商品 ID，可套用同一店铺、分类和标记；Excel 模板导入也在这一页
- 看板：累计已售、今日、昨日、上小时。缺基线为「—」，中途开始监控标 `*`
- 单品页 `/xhs/:productId`：按小时、近 7 日增量
- 定时默认关闭，在「设置」页选间隔，或每天、每周、每月的时间，存成 Cron（默认每小时整点 `0 * * * *`，北京时间），job id `xhs_monitor`
- 「失败列表」放临时没采到的商品，可重试、忽略或删除。「下架列表」只回看页面已写明下架或违规的商品，不再采集
- 商品可归到店铺，并带一个分类和若干标记。侧栏「店铺」按店加总。可用 Excel 模板批量导入

---

## 三、后端 API 端点清单

### 3.1 应用级

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查（免认证），返回 `{"status":"healthy"}` |
| POST | `/auth/status` | 登录校验，Body `{username, password}` |
| GET | `/` | Vue SPA 首页（`dist/index.html`） |
| GET | `/{path}` | SPA catch-all（支持 History 路由；静态资源后缀返回 404） |
| GET | `/static/*` | 静态资源挂载 |
| GET | `/assets/*` | 前端构建产物（`dist/assets`） |

### 3.2 任务（`/api/tasks`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/tasks` | 所有任务（含调度状态） |
| GET | `/api/tasks/{id}` | 单任务详情 |
| POST | `/api/tasks/` | 创建任务（立即重载调度器） |
| POST | `/api/tasks/generate` | 创建任务（AI 模式返回 202 + job，异步生成；关键词模式直接返回 200 + 任务） |
| GET | `/api/tasks/generate-jobs/{job_id}` | 查询 AI 生成作业进度 |
| PATCH | `/api/tasks/{id}` | 更新任务（切 AI 模式或改描述时自动重生成 criteria） |
| DELETE | `/api/tasks/{id}` | 删除任务（级联停进程、删结果/价格/日志） |
| POST | `/api/tasks/start/{id}` | 启动任务 |
| POST | `/api/tasks/stop/{id}` | 停止任务 |

### 3.3 结果（`/api/results`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/results/files` | 结果文件列表 |
| GET | `/api/results/files/{filename}` | 下载 NDJSON |
| DELETE | `/api/results/files/{filename}` | 删除结果文件及其记录 |
| GET | `/api/results/{filename}` | 分页读取（筛选/排序/分页） |
| GET | `/api/results/{filename}/insights` | 价格趋势洞察 |
| GET | `/api/results/{filename}/export` | 导出 CSV |
| PATCH | `/api/results/{filename}/items/{item_id}/status` | 更新商品状态（active/hidden/expired） |
| GET | `/api/results/{filename}/blacklist-rules` | 获取黑名单规则 |
| PUT | `/api/results/{filename}/blacklist-rules` | 更新黑名单规则 |

**查询参数**：`page`、`limit`(1-100)、`recommended_only`、`ai_recommended_only`、`keyword_recommended_only`（与 AI 互斥）、`include_hidden`、`sort_by`(crawl_time/publish_time/price/keyword_hit_count)、`sort_order`(asc/desc)

### 3.4 账号（`/api/accounts`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/accounts` | 账号列表（name + path） |
| GET | `/api/accounts/{name}` | 账号详情（含 content） |
| POST | `/api/accounts` | 创建账号（`{name, content}`） |
| PUT | `/api/accounts/{name}` | 更新账号内容 |
| DELETE | `/api/accounts/{name}` | 删除账号 |

### 3.5 收录（`/api/collections`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/collections` | 收录列表 |
| GET | `/api/collections/lookup` | 查询某结果是否已收录 |
| POST | `/api/collections` | 收录商品（result_item_id / result_filename+item_id 二选一），可选异步拉 SKU |
| GET | `/api/collections/{id}` | 收录详情 |
| POST | `/api/collections/{id}/refresh-skus` | 刷新 SKU |
| DELETE | `/api/collections/{id}` | 取消收录 |

### 3.6 仪表盘（`/api/dashboard`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/dashboard/summary` | 仪表盘快照（summary + task_summaries + recent_activities + focus_file） |

### 3.7 日志（`/api/logs`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/logs` | 增量读取（基于字节位置游标 `from_pos`） |
| GET | `/api/logs/tail` | 按行分页读取尾部（历史加载） |
| DELETE | `/api/logs` | 清空指定任务日志 |

### 3.8 设置（`/api/settings`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET / PUT | `/api/settings/ai` | AI 设置读写 |
| POST | `/api/settings/ai/test` | 测试 AI 连接（发送 "Reply with OK only."） |
| GET / PUT | `/api/settings/notifications` | 通知设置读写 |
| POST | `/api/settings/notifications/test` | 测试通知（可单渠道/全渠道） |
| GET / PUT | `/api/settings/rotation` | 轮换设置读写 |
| GET | `/api/settings/status` | 系统状态汇总 |

### 3.9 提示词（`/api/prompts`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/prompts` | 提示词文件列表 |
| GET | `/api/prompts/{filename}` | 获取内容（防路径穿越） |
| PUT | `/api/prompts/{filename}` | 更新内容 |

### 3.10 登录态（`/api/login-state`）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/login-state` | 保存根登录态 `xianyu_state.json` |
| DELETE | `/api/login-state` | 删除根登录态 |

### 3.11 WebSocket

| 端点 | 事件 |
|------|------|
| `/ws` | `task_status_changed`、`tasks_updated`、`results_updated` |

### 3.12 卖家订阅（`/api/seller-subscriptions`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/seller-subscriptions` | 订阅列表（含概览） |
| POST | `/api/seller-subscriptions` | 添加订阅 |
| PATCH | `/api/seller-subscriptions/schedule` | 更新全局 Cron/限额/账号策略 |
| POST | `/api/seller-subscriptions/run` | 手动启动采集子进程 |
| PATCH | `/api/seller-subscriptions/{id}` | 更新单条订阅 |
| DELETE | `/api/seller-subscriptions/{id}` | 删除订阅，并级联清理该卖家名下的商品/画像/健康度数据（返回 `deleted` 各表删除行数） |
| GET | `/api/seller-subscriptions/profiles` | 最新卖家画像列表 |
| GET | `/api/seller-subscriptions/items` | 商品分页列表（`seller_id`/`search`/`sort_by`/`sort_order`） |
| GET | `/api/seller-subscriptions/items/{item_id}/detail` | 商品详情（指标 + 详情 API） |
| GET | `/api/seller-subscriptions/detail/{seller_user_id}` | 卖家订阅 + 画像 |
| GET | `/api/seller-subscriptions/metrics` | 商品指标时序 |
| GET | `/api/seller-subscriptions/stats` | 统计（卖家数/商品数/调度配置） |

### 3.13 店铺分析（`/api/shop-analytics`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/shop-analytics/dashboard` | **主看板**（`period=today\|7d`，默认 today）；订阅日指标聚合 |
| GET | `/api/shop-analytics/overview` | 旧 datacompass 概览（`cycle=1d\|7d\|30d`），主页面不再调用 |
| GET | `/api/shop-analytics/flow` | 旧流量明细 |
| GET | `/api/shop-analytics/distribution` | 旧分布（`type=source\|category\|time\|region`） |
| GET | `/api/shop-analytics/trend` | 旧指标趋势（`metric`、`days`、`cycle`） |
| POST | `/api/shop-analytics/collect` | 触发 datacompass 采集任务（本页 UI 不调用） |

### 3.14 小红书监控（`/api/xhs`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/xhs/products` | 看板：还在监控、最近一次没失败也没下架的商品 |
| GET | `/api/xhs/failures` | 临时失败 |
| POST | `/api/xhs/failures/ignore` | 忽略失败并回到看板 |
| GET | `/api/xhs/delisted` | 已下架，不再采集 |
| POST | `/api/xhs/products` | 添加公开商品链接，可带店铺、分类、标记 |
| GET | `/api/xhs/products/import-template` | 下载 Excel 模板 |
| POST | `/api/xhs/products/import` | 按模板导入，单次最多 500 行 |
| PATCH | `/api/xhs/products/{id}` | 修改店铺、分类、标记 |
| GET | `/api/xhs/shops` | 店铺合计，含未归店 |
| POST | `/api/xhs/shops` | 按店名创建，同名返回已有店 |
| GET | `/api/xhs/shops/{id}` | 单店合计和商品 |
| DELETE | `/api/xhs/products/{id}` | 停止监控（快照保留） |
| POST | `/api/xhs/products/{id}/collect` | 采集单个公开页 |
| POST | `/api/xhs/collect` | 采集全部；461 或登录墙停止本轮 |
| GET | `/api/xhs/products/{id}/series` | `kind=hourly\|daily` |
| GET/PATCH | `/api/xhs/schedule` | 独立 Cron，默认关闭 |
| GET | `/api/xhs/cover` | 主图代理，只允许小红书图床 |

---

## 四、任务配置字段详解

### 4.1 字段表

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_name` | str | ✅ | 任务名称（唯一） |
| `keyword` | str | ✅ | 搜索关键词 |
| `enabled` | bool | ✅ | 是否启用 |
| `description` | str | AI 模式✅ | 购买需求描述（AI 模式用于生成分析标准） |
| `decision_mode` | enum | ✅ | `ai` / `keyword` |
| `analyze_images` | bool | 否 | 是否分析图片（AI 模式） |
| `keyword_rules` | list[str] | keyword 模式✅ | 关键词规则（OR 逻辑） |
| `min_price` / `max_price` | str | 否 | 价格区间 |
| `max_pages` | int | 否 | 最大翻页数 |
| `cron` | str | 否 | Cron 表达式（空=手动） |
| `account_strategy` | enum | 否 | `auto` / `fixed` / `rotate` |
| `account_state_file` | str | fixed 模式✅ | 绑定账号文件 |
| `personal_only` | bool | 否 | 仅个人闲置 |
| `free_shipping` | bool | 否 | 包邮 |
| `new_publish_option` | str | 否 | 新发布：`1小时内`/`1天内`/`3天内`/`7天内`/`14天内` 等 |
| `region` | str | 否 | 区域，格式 `省/市/区`（如 `江苏/南京/全南京`） |
| `ai_prompt_base_file` | str | 否 | 基础提示词（默认 `prompts/base_prompt.txt`） |
| `ai_prompt_criteria_file` | str | 否 | 判定标准提示词 |
| `is_running` | bool | 否 | 运行状态（服务端维护） |

### 4.2 前端 Cron 预设（TaskForm）

手动 / 每5分钟 / 每15分钟 / 每30分钟 / 每小时 / 每2小时 / 每6小时 / 每日8点 / 每日12点 / 每日18点 / 每日20点 / 每日8+12+18点 / 工作日9点 / 周末10点，或自定义表达式。

### 4.3 区域筛选

省/市/区三级联动选择器，数据来自内置 `web-ui/src/data/goofishRegions.json`（闲鱼页面快照）。另有快捷区域：全国 / 珠三角 / 江浙沪 / 京津冀 / 东三省。**注意**：区域筛选会显著缩小结果集，默认留空。

### 4.4 校验规则

- AI 模式必须提供 `description`；关键词模式必须 ≥1 条 `keyword_rules`
- `fixed` 账号策略必须选择账号文件
- Cron 表达式非法会报错
- 价格自动转字符串、空/`"null"`/`"undefined"` 归一为 `None`

---

## 五、AI 能力

### 5.1 AI 提供方

| 提供方 | 环境变量 | 说明 |
|--------|----------|------|
| `openai`（默认） | `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL_NAME` | 任何 OpenAI 兼容网关（OpenAI、ModelScope、DeepSeek 等）；模型须支持图片 |
| `cursor` | `CURSOR_API_KEY` / `CURSOR_MODEL_NAME` / `CURSOR_RUNTIME` | Cursor SDK；`local`/`cloud`/自动三种运行模式 |

切换方式：改 `AI_PROVIDER` 重启即可；Web UI「系统设置 → AI」可视化配置 + 测试连接。

### 5.2 三类 AI 用途

| 用途 | 触发点 | 说明 |
|------|--------|------|
| **AI 生成分析标准** | AI 模式创建/刷新任务时 | `prompt_utils.generate_criteria`：根据用户描述 + 参考范例生成 `{keyword}_criteria.txt`，后台 job 展示 6 步进度 |
| **AI 品类过滤（门禁）** | 每条商品完整分析前 | `listing_ai_filter.filter_listing_by_ai`：轻量判断是否目标品类（最多 2 张图、temperature 0.05），剔除明显非目标商品 |
| **完整 AI 图文分析** | 通过门禁的每条商品 | `ai_handler.get_ai_analysis`：下载全部图片 + 商品 JSON + 分析标准 → 输出推荐决策 |

### 5.3 分析输出结构

```json
{
  "prompt_version": "V6.3",
  "is_recommended": true,
  "reason": "...",
  "risk_tags": ["无保修", "仅自提"],
  "criteria_analysis": {"seller_type": "个人卖家", "...": "..."},
  "value_score": 82,
  "value_summary": "性价比高"
}
```

### 5.4 兼容与降级

- 自动在 Responses API / Chat Completions API 间回退
- 自动移除不支持的 `response_format` / `temperature`
- 空响应/JSON 解析失败/格式校验失败 → 重试（≤4 次）
- `AI_DEBUG_MODE=true` 打印完整请求/响应诊断
- 无图模式：自动追加 "本次未提供商品图片…" 提示
- `SKIP_AI_ANALYSIS=true`：跳过 AI 直接全部推荐（测试用）

---

## 六、通知渠道

### 6.1 渠道一览

| 渠道 | 启用条件 | 消息形态 |
|------|----------|----------|
| **ntfy** | `NTFY_TOPIC_URL` | POST 纯文本 + `Title`/`Priority: urgent`/`Tags` 头 |
| **Bark** | `BARK_URL` | POST JSON `{title, body, url, level:timeSensitive, group:闲鱼监控}` |
| **Gotify** | `GOTIFY_URL` + `GOTIFY_TOKEN` | POST multipart 到 `{url}/message?token=`，priority=5 |
| **企业微信** | `WX_BOT_URL` | POST markdown，校验 `errcode` |
| **Telegram** | `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` | POST `sendMessage`，HTML 格式 + 链接；支持 `TELEGRAM_API_BASE_URL` 反代 |
| **通用 Webhook** | `WEBHOOK_URL` | GET/POST，可配置 headers/query/body 模板 |

### 6.2 通知内容模板

统一标题带 emoji（截断 30 字），内容含：标题、价格、推荐原因、桌面/移动链接、商品主图。

Webhook 模板变量：`{{title}}`、`{{content}}`、`{{price}}`、`{{reason}}`、`{{desktop_link}}`、`{{mobile_link}}`（也支持 `${var}` 风格）。

### 6.3 附加功能

- `PCURL_TO_MOBILE`：PC 链接转移动端分享链接（默认建议开启）
- Web UI 分渠道「测试」与「清除」（敏感字段置 null）
- 全渠道并发发送，逐渠道返回成功/失败

---

## 七、账号与代理轮换

### 7.1 账号

| 能力 | 说明 |
|------|------|
| 登录态管理 | Web UI 导入/更新/删除 `state/{name}.json`（支持增强快照：cookies + env + headers + storage） |
| 策略 | `auto`（根文件优先）/ `fixed`（固定）/ `rotate`（账号池轮换） |
| 轮换模式 | `per_task`（任务级固定）/ `on_failure`（失败才换） |
| 黑名单 TTL | 失败账号临时剔除（`ACCOUNT_BLACKLIST_TTL`，默认 300s） |
| 自动恢复 | Cookie 更新（mtime 变化）→ FailureGuard 自动放行 |

### 7.2 代理

| 能力 | 说明 |
|------|------|
| 代理池 | `PROXY_POOL`（逗号分隔），支持 HTTP/HTTPS/SOCKS5 |
| 轮换模式 | `per_task` / `on_failure` |
| 重试与黑名单 | `PROXY_ROTATION_RETRY_LIMIT`、`PROXY_BLACKLIST_TTL` |
| AI 请求代理 | `PROXY_URL` 单独为 AI 请求指定代理 |
| 浏览器代理 | 爬虫启动时套用所选代理 |

---

## 八、结果管理

### 8.1 筛选与排序

- 筛选：AI 推荐、关键词推荐（两者互斥）、包含已隐藏
- 排序：爬取时间 / 发布时间 / 价格 / 关键词命中数 × 升/降序
- 分页：`page` + `limit`（1–100）

### 8.2 价格洞察（price_history_service）

- 数据来源：每次任务运行记录的 `price_snapshots` 价格快照
- **性价比评分算法**（0–100）：
  - 基础分 50
  - 低于市场均价：每低 1% +0.6（上限 +60）
  - 低于历史最高价：每低 1% +0.2（上限 +20）
  - 等于历史最低价：+8
- **性价比标签**：≥65 高性价比 / ≥50 值得关注 / ≥40 价格正常 / <40 价格偏高
- 洞察内容：观察次数、当前/均价/中位数/最低/最高价、价格变化、首末次出现时间、市场均价/中位数、日趋势

### 8.3 黑名单（result_blacklist_service）

- 按结果文件配置关键词列表
- 匹配规则：
  - `re:` 前缀 → 正则（忽略大小写）
  - 纯 ASCII 数字字母 → 完整词边界匹配（避免 `Q1` 误中 `Q1R5`）
  - 其他中文/混合 → 子串包含匹配
- 命中的商品自动隐藏（`_hidden_reason = rule`）

### 8.4 商品状态

每条商品可标记 `active` / `hidden` / `expired`，隐藏原因可为 `manual`（手动）/ `expired`（过期）/ `rule`（黑名单）。

### 8.5 导出

- CSV：25 列（任务名、关键词、商品 ID、标题、售价、发布时间、卖家、推荐状态、分析来源、原因、价格观察次数、最低/最高价、市场均价、性价比分数/标签、链接等）
- NDJSON：完整原始记录（含 raw_json）

---

## 九、商品收录与 SKU

### 9.1 收录流程

1. 结果页点击「收藏」→ `collect_result_item` 写入 `collected_items` 表
2. 默认异步触发 SKU 抓取（`sku_fetch_status`: pending → running → done/failed）
3. 收藏详情页可手动「刷新 SKU」、查看规格/价格、打开闲鱼链接

### 9.2 SKU 抓取（item_sku_fetch_service）

- 用 Playwright 打开商品详情页，注册 response 监听器捕获 SKU 相关 MTOP 接口
- 提取 `{sku_id, label, price, price_display, properties, in_stock, source}`
- 三层兜底解析：递归收集 SKU 列表 → CPV 映射 → 标题片段解析
- 支持无 SKU 时从标题解析「颜色分类/长度」等规格

---

## 十、命令行功能

### 10.1 爬虫 CLI（spider_v2.py）

```bash
python spider_v2.py                          # 运行所有启用任务（从数据库读取）
python spider_v2.py --task-name "MacBook"    # 运行指定任务（调度器/Web 启动用）
python spider_v2.py --seller-subscriptions   # 运行卖家订阅采集（独立子进程入口）
python spider_v2.py --debug-limit 3          # 调试模式：每任务最多处理 3 个新商品
python spider_v2.py --config custom.json     # 使用 JSON 配置文件（兼容旧版）
```

`task_type` 分支：`keyword_search`（默认）| `seller_subscription` | `shop_datacompass`。

行为要点：
- 无 `--config` 时从 `create_task_repository()` 读取任务（Postgres）
- 启动前校验登录态（根 state 文件 / 绑定账号 / state 目录，三者全无则退出）
- 信号处理：SIGTERM/SIGINT 优雅停止
- `--debug-limit`：非无头 + 终端下结束后等待回车

### 10.2 运维脚本

```bash
python3 -m scripts.verify_database                 # 验证数据库连通与表读写
python3 -m scripts.migrate_sqlite_to_postgres      # SQLite → Postgres 一次性迁移
   --source data/app.sqlite3 --dry-run             # 预演
python3 -m scripts.check_env_keys                  # 检查环境变量是否注入（脱敏）
python3 -m scripts.cleanup_orphan_seller_data      # 报告删除订阅后残留的孤儿商品数据
   --apply                                        # 确认后真正删除
   --seller <user_id>                             # 只处理指定卖家
```

> 卖家订阅删除已改为**级联删除**（商品、日指标、画像、健康度记录一并清理）。
> 上述脚本只用于清理改动之前遗留的孤儿数据。

### 10.3 桌面启动器

`desktop_launcher.py`：PyInstaller 打包单文件入口，启动 FastAPI 并自动打开浏览器（`http://127.0.0.1:{port}`）。

---

## 十一、Chrome 扩展功能

| 功能 | 说明 |
|------|------|
| 一键采集登录态 | 点击「获取环境+登录状态」，生成完整 JSON |
| 采集内容 | cookies（含 HttpOnly）、env（navigator/screen/intl）、headers（白名单）、storage（localStorage/sessionStorage，>4KB 丢弃记录） |
| HttpOnly 读取 | 通过 `chrome.cookies` API 绕过 JS 限制 |
| 请求头捕获 | `webRequest.onBeforeSendHeaders` + 主动 `fetch` 探测 |
| 一键复制 | JSON 复制到剪贴板 → 粘贴到 Web UI 账号管理 |
| 隐私 | 仅本地生成，不上传任何服务器；配套隐私政策页 `xianyu-login-state-privacy.html` |

---

## 十二、配置项完整清单

### 12.1 AI 与模型

| 变量 | 默认 | 说明 |
|------|------|------|
| `AI_PROVIDER` | `openai` | `openai` / `cursor` |
| `OPENAI_API_KEY` | - | OpenAI 兼容 Key |
| `OPENAI_BASE_URL` | `https://api-inference.modelscope.cn/v1/` | 接口地址 |
| `OPENAI_MODEL_NAME` | `XiaomiMiMo/MiMo-V2-Flash` | 模型（须支持图片） |
| `CURSOR_API_KEY` | - | Cursor Key |
| `CURSOR_MODEL_NAME` | `composer-2.5` | Cursor 模型 |
| `CURSOR_RUNTIME` | 空 | `local`/`cloud`/空(自动) |
| `CURSOR_LOCAL_CWD` | `.` | local 工作目录 |
| `CURSOR_CLOUD_REPOS` | - | cloud 仓库列表 |
| `PROXY_URL` | - | AI 请求代理 |
| `AI_DEBUG_MODE` | `false` | AI 调试 |
| `ENABLE_THINKING` | `false` | 思考模式 |
| `ENABLE_RESPONSE_FORMAT` | `true` | 结构化 JSON 输出 |
| `SKIP_AI_ANALYSIS` | `false` | 跳过 AI 分析 |
| `AI_LISTING_FILTER_ENABLED` | `true` | AI 品类过滤开关 |

### 12.2 通知

| 变量 | 默认 | 说明 |
|------|------|------|
| `NTFY_TOPIC_URL` | - | ntfy 主题 |
| `BARK_URL` | - | Bark |
| `WX_BOT_URL` | - | 企业微信机器人 |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | - | Telegram |
| `TELEGRAM_API_BASE_URL` | `https://api.telegram.org` | Telegram 反代 |
| `GOTIFY_URL` / `GOTIFY_TOKEN` | - | Gotify |
| `WEBHOOK_URL` | - | Webhook 地址 |
| `WEBHOOK_METHOD` | `POST` | GET/POST |
| `WEBHOOK_CONTENT_TYPE` | `JSON` | JSON/FORM |
| `WEBHOOK_HEADERS` | - | 自定义头（JSON） |
| `WEBHOOK_QUERY_PARAMETERS` | - | 查询参数（支持模板） |
| `WEBHOOK_BODY` | - | 请求体（支持模板） |
| `PCURL_TO_MOBILE` | `true` | PC 链接转移动端 |

### 12.3 数据库与 Web

| 变量 | 默认 | 说明 |
|------|------|------|
| `DATABASE_URL` | - | PostgreSQL 连接串（必填） |
| `SERVER_PORT` | `8000` | 服务端口 |
| `WEB_USERNAME` / `WEB_PASSWORD` | `admin` / `admin123` | Web 登录（生产务必改） |

### 12.4 爬虫

| 变量 | 默认 | 说明 |
|------|------|------|
| `RUN_HEADLESS` | `true` | 无头模式（Docker 必须 true） |
| `LOGIN_IS_EDGE` | `false` | 本地用 Edge 内核 |
| `STATE_FILE` | `xianyu_state.json` | 根登录态 |
| `ACCOUNT_STATE_DIR` | `state` | 账号目录 |
| `IMAGE_DOWNLOAD_CONCURRENCY` | `3` | 图片下载并发 |

### 12.5 失败保护与轮换

| 变量 | 默认 | 说明 |
|------|------|------|
| `TASK_FAILURE_THRESHOLD` | `3` | 连续失败阈值 |
| `TASK_FAILURE_PAUSE_SECONDS` | `86400` | 熔断暂停时长 |
| `TASK_FAILURE_GUARD_PATH` | `logs/task-failure-guard.json` | 状态文件 |
| `TASK_LOG_RETENTION_DAYS` | `7` | 日志保留天数 |
| `ACCOUNT_ROTATION_ENABLED` / `MODE` / `RETRY_LIMIT` / `BLACKLIST_TTL` | - | 账号轮换 |
| `PROXY_ROTATION_ENABLED` / `MODE` / `RETRY_LIMIT` / `BLACKLIST_TTL` | - | 代理轮换 |
| `PROXY_POOL` | - | 代理池 |

---

## 十三、测试体系

### 13.1 组织

| 层级 | 目录 | 内容 |
|------|------|------|
| 单元测试 | `tests/unit/`（约 40 个文件） | AI、解析、关键词、卖家订阅、店铺罗盘、失败保护等 |
| 集成测试 | `tests/integration/`（11 个） | tasks/results/settings/dashboard/seller-subscriptions/shop-analytics/accounts/collections/logs API、CLI、解析管道 |
| Live 冒烟 | `tests/live/`（3 个，默认 skip） | 真实账号+AI+流量（`RUN_LIVE_TESTS=1`） |
| 前端 smoke | `web-ui/src/**/*.test.ts`（9 个） | 路由、i18n、工具函数（Vitest） |
| 根级 | `tests/` | FailureGuard、前端构建路径 |
| 替身 | `tests/fakes/memory_task_repository.py` | 内存任务仓储 |
| 样例数据 | `tests/fixtures/` | 搜索/卖家/评价/配置样例 |

当前约 **186** 后端用例（183 离线 + 3 live）+ **9** 前端 Vitest smoke。详见 [tests/README.md](../tests/README.md)、[web-ui/README.md](../web-ui/README.md)。

### 13.2 运行

```bash
python -m pytest -q                               # 全部离线测试（推荐）
python -m pytest --cov=src                        # 覆盖率
python -m pytest tests/unit/test_utils.py::test_safe_get_nested_and_default
./run_live_smoke.sh --keyword "MacBook Pro M2"    # 真实流量冒烟
```

CI：`.github/workflows/pytest.yml`（后端）与 `.github/workflows/web-ui.yml`（前端）在 push/PR 时自动运行。

### 13.3 隔离设计

- 测试使用 `data/.pytest-env`，不读仓库 `.env`
- 任务 API 测试用 `InMemoryTaskRepository`；部分结果/卖家测试使用 PG fixture 或 mock
- Live 测试在临时目录运行、清空通知环境变量
- Windows 建议 `--capture=no`（已在 `pyproject.toml` 默认启用）

---

## 十四、错误码与诊断

### 14.1 搜索诊断

当搜索结果为空时，爬虫输出 `[搜索诊断]`（ret、data_keys、resultList 长度）；`AI_DEBUG_MODE=true` 打印完整 JSON。常见 `ret` 含义：

| ret | 含义 | 处理 |
|-----|------|------|
| `ILLEGAL_ACCESS` | Cookie 失效/签名不匹配/headless 被风控 | 重新导入登录态；检查风控 |
| `FAIL_SYS_*` | 系统级错误 | 结合上下文排查 |

### 14.2 登录与风控诊断

| 现象 | 原因 | 处理 |
|------|------|------|
| 跳转 passport.goofish.com / mini_login | 登录态失效 | 重新导出并更新 Cookie |
| baxia-dialog / 中间件弹窗 | 验证码风控 | 降低频率、`RUN_HEADLESS=false`、用增强快照 |
| 任务连续失败被暂停 | FailureGuard 熔断 | 更新 Cookie 自动恢复或查看 `logs/task-failure-guard.json` |

### 14.3 运行日志位置

| 内容 | 路径 |
|------|------|
| 任务日志 | `logs/{task_id}_{task_name}.log` |
| AI 分析日志 | `logs/ai/{timestamp}.log`（保留 1 天） |
| 失败保护状态 | `logs/task-failure-guard.json` |
| 崩溃备份 | `logs/task-failure-guard.json.corrupt.{ts}` |

---

## 附：功能矩阵速查

| 功能 | Web UI | REST API | 爬虫 | 配置 |
|------|:------:|:--------:|:----:|:----:|
| 创建/编辑任务 | ✅ | ✅ | - | config.json |
| AI 生成标准 | ✅（进度弹窗） | ✅（job） | - | prompts/ |
| 定时调度 | ✅ | ✅ | - | cron 字段 |
| 启动/停止 | ✅ | ✅ | ✅ | - |
| 登录态管理 | ✅ | ✅ | ✅ | state/ |
| 通知配置 | ✅ | ✅ | - | .env |
| 结果浏览/导出 | ✅ | ✅ | - | - |
| 收藏/SKU | ✅ | ✅ | ✅ | - |
| 黑名单 | ✅ | ✅ | - | - |
| 日志 | ✅ | ✅ | ✅ | - |
| 系统状态 | ✅ | ✅ | - | - |
| 卖家订阅 | ✅ | ✅ | ✅ | seller_subscriptions 表 |
| 店铺分析看板 | ✅ | ✅ | ✅ | seller_item_daily_metrics；旧 datacompass 接口保留 |
