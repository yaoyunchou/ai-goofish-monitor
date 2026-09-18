# Web UI 变更日志

## 2026-09-18

### fix(seller-subscription): 采集控制台展示下次执行并提示 job 未挂上

- 调度卡片增加「下次执行」：有 `next_run_at` 按时区格式化；enabled 且为空时醒目提示保存调度或重启后端
- 类型 `SellerSubscriptionSchedule` / stats 补 `next_run_at`；中英 i18n 同步

## 2026-09-17

### feat(logs): 卖家订阅采集日志接入 Web

- `LogsView` 下拉新增「卖家订阅采集」（`task_id=-1`），支持增量刷新与清空
- `SELLER_SUBSCRIPTION_CONSOLE_LOG=true` 时，`SellerCollectionView` 底部展示实时日志（开发调试用）；关闭时显示灰色提示条
- 修改前端后需 `cd web-ui && npm run build` 更新 `dist/`，否则页面无变化

### fix(ui): Switch 组件 checked/modelValue 绑定错误

- reka-ui Switch 使用 `modelValue`，`:checked` 只会落到原生 HTML 属性导致 `data-state=unchecked` 假象
- `Switch.vue` 兼容 `checked`/`update:checked` 并映射到 `modelValue`；卖家订阅/调度弹窗改用 `v-model` 或 `:model-value`

### fix(seller-subscription): 列表开关与编辑弹窗状态不一致

- 开关保存后以 PATCH 响应为准更新列表；`normalizeSubscriptionEnabled` 统一布尔解析
- 编辑弹窗打开时重新拉取行数据 + `Switch :key` 强制重挂载，避免显示旧状态
- 开关保存中禁用「编辑」按钮，防止读到未落库的 enabled

### ux(seller-subscription): 参与采集开关说明与反馈

- 列表顶部增加说明文案；开关列显示「采集中/已暂停」+ 悬停提示
- 切换成功弹出 Toast；列表增加「编辑」弹窗（备注 + 参与采集）
- 卖家详情页开关同样增加标签与 Toast

### fix(seller-collection): 采集中状态丢失、卖家数偏少、无头开关回显错误

- 返回采集控制台时若仍在跑则自动恢复 5s 轮询
- 无头模式：`run_headless` 为 null 时回显继承 `run_headless_effective`；保存后不再被 `load()` 覆盖
- 卖家数由后端改为统计订阅表条目

### fix(seller-subscription): 采集时间显示偏差（+8 小时）

- 新增 `src/lib/datetime.ts`：`formatShanghaiTime` / `parseAppDateTime`
- 卖家订阅相关页面统一按 `Asia/Shanghai` 展示采集时间，无时区后缀的字符串按北京时间解析

### fix(seller-subscription): 卖家订阅启用/禁用开关不生效

- `SellerSubscriptionView` / `SellerDetailView`：`Switch` 使用 `(checked) => setEnabled(..., checked)`，不再 `!row.enabled` 翻转
- 增加 `togglingIds` / `isTogglingEnabled` 防重复提交；与调度弹窗 `v-model:checked` 修复同一类受控组件问题

### fix(seller-collection): 无头模式保存不生效

- DB：`ensure_incremental_schema` 补齐 `run_headless` 列（旧库仅有 Supabase 初始 migration 时缺列）
- 新增 Supabase migration `20260917100000_seller_schedule_run_headless.sql`
- `SellerScheduleDialog` Switch 改为 `v-model:checked`（修复开关状态未写入 ref）
- 保存后 `SellerCollectionView` 重新拉取 stats 确认持久化

### feat(seller-collection): 采集调度增加无头模式配置

- `SellerScheduleDialog` 新增「无头模式」开关，保存 `run_headless` 到调度配置
- `SellerCollectionView` 调度卡片展示当前浏览器模式（无头/有头）
- API 类型 `SellerSubscriptionSchedule` 增加 `run_headless` / `run_headless_effective`
- i18n：`sellerSubscription.runHeadless*`、`sellerCollection.scheduleCard.browserMode*`

### chore(test): 阶段四 Vitest smoke + README

- 新增 `README.md`：开发指南、目录结构、路由表、与后端集成说明
- 安装 Vitest + jsdom；`npm test` 运行 9 个 smoke 用例（utils、goofish、router、i18n）
- `vite.config.ts` 增加 `test` 配置；`tsconfig.node.json` 引入 `vitest/config` 类型
- 修复 `useTaskGenerationJob` 轮询 timer 类型（`number | null`，兼容 DOM lib）
- CI 工作流 `.github/workflows/web-ui.yml`

## 2026-09-16

### feat(seller-subscription): 详情页展示 item_detail_api_raw 完整 API JSON

- 详情 API 响应单独展示 `mtop.taobao.idle.pc.detail` 归档数据
- 与 result_items 摘要 JSON 分区显示，避免混淆

### feat(seller-subscription): 商品详情页取数测试 + 展示爬虫原始 JSON

- 新增 `GET /api/seller-subscriptions/items/{item_id}/detail`：合并 `seller_item_metrics` 时序与 `result_items.raw_json`
- 详情页展示主图/图集、描述、字段统计（图片数、描述长度、是否含 SKU 字段）
- 默认展开「爬虫原始 JSON」区块，支持复制，便于核对爬虫实际入库数据

### feat(seller-subscription): 商品列表可点击查看详情，支持跳转闲鱼原页面

- 新增路由 `/seller-subscriptions/items/:itemId` 与 `SellerItemDetailView.vue`
- 商品列表行可点击，进入详情页展示价格/想要/浏览/状态与指标趋势图
- 详情页右上角「查看原页面」按钮，新标签打开 `https://www.goofish.com/item?id={item_id}`
- 新增 `lib/goofish.ts` 统一拼接闲鱼商品链接
- `SellerItemsView` / `SellerDetailView` 接入行点击跳转；返回按钮按来源回到列表或卖家详情

## 2026-08-04

### chore(settings): 系统状态仅展示 PostgreSQL

- 移除 `sqlite_path` 展示；数据库仅显示 `database_url` 主机/库名

## 2026-08-03

### feat(settings): 系统状态页展示运行环境摘要

- `GET /api/settings/status` 增加 `runtime`（配置来源、数据库驱动、不含密钥）
- 设置 → **系统状态** 表格展示关键环境变量


- 结果卡片新增「收录」按钮，收录后跳转 `/results/collected/:id`
- 后端 `collected_items` 表 + `/api/collections`：收录后 Playwright 拉取详情页 SKU/价格
- 收录详情页展示规格表格，支持重新拉取 SKU
- 结果 API 返回 `_result_item_id` / `_result_filename` 供收录定位

## 2026-07-30

### chore(ai): Cursor SDK 分支同步与 Cloud 运行时

- 与后端 `AI_PROVIDER=cursor` 能力对齐；设置页已支持 Cursor SDK（见 `SettingsView.vue`，分支 `cursor/sync-cursor-sdk-dc12`）
- API `GET /api/settings/ai` 增加 `CURSOR_RUNTIME_EFFECTIVE`，便于展示 Cloud Agent 内自动解析的 runtime
