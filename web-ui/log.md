# Web UI 变更日志

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
