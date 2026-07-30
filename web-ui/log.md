# Web UI 变更日志

## 2026-07-30

### chore(ai): Cursor SDK 分支同步与 Cloud 运行时

- 与后端 `AI_PROVIDER=cursor` 能力对齐；设置页已支持 Cursor SDK（见 `SettingsView.vue`，分支 `cursor/sync-cursor-sdk-dc12`）
- API `GET /api/settings/ai` 增加 `CURSOR_RUNTIME_EFFECTIVE`，便于展示 Cloud Agent 内自动解析的 runtime
