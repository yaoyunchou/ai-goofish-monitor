# Web UI 变更日志

## 2026-08-04

### chore(tasks): 后端新增「机乐堂30w多口充电头」任务配置

- 无前端代码变更；任务可在 Web「任务管理」中查看、手动运行或调整 cron/价格
- 分析标准文件 `prompts/机乐堂30w多口充电头_criteria.txt` 可在任务编辑页跳转查看

## 2026-08-03

### feat(results): 结果页收录与 SKU 详情

- 结果卡片新增「收录」按钮，收录后跳转 `/results/collected/:id`
- 后端 `collected_items` 表 + `/api/collections`：收录后 Playwright 拉取详情页 SKU/价格
- 收录详情页展示规格表格，支持重新拉取 SKU
- 结果 API 返回 `_result_item_id` / `_result_filename` 供收录定位

## 2026-07-30

### chore(ai): Cursor SDK 分支同步与 Cloud 运行时

- 与后端 `AI_PROVIDER=cursor` 能力对齐；设置页已支持 Cursor SDK（见 `SettingsView.vue`，分支 `cursor/sync-cursor-sdk-dc12`）
- API `GET /api/settings/ai` 增加 `CURSOR_RUNTIME_EFFECTIVE`，便于展示 Cloud Agent 内自动解析的 runtime
