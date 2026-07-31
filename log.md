# 变更日志

### feat(scraper): 分析代理增加统一 AI 品类过滤（门禁）

- 新增 `src/services/listing_ai_filter.py` 与 `prompts/listing_ai_filter_system.txt`
- `ItemAnalysisDispatcher` 在关键词/完整 AI 分析前执行过滤，剔除「仅数据线」等非目标品类（`analysis_source=ai_filter`）
- 环境变量 `AI_LISTING_FILTER_ENABLED`（默认 `true`）；任务级可用 `enable_ai_listing_filter` 覆盖
- 购买意图取自任务 `description`（空则回退搜索 `keyword`）；过滤阶段最多下载 2 张图辅助识别

## 2026-07-31

### chore(tasks): 机乐堂 30W 任务改为 AI 判定并补充 criteria

- 任务「机乐堂30W充电头」由关键词 OR 模式改为 `decision_mode=ai`，启用看图分析
- 新增 `prompts/机乐堂_30w_充电头_criteria.txt`（品牌一票否决、排除卡斐乐等非机乐堂）
- 结果集 `机乐堂_30w_充电头_full_data.jsonl` 配置展示黑名单关键词，便于结果页过滤误匹配

## 2026-07-30

### fix(ai): 适配 cursor-sdk 1.0.26 AsyncClient 桥接调用

- `cursor_transport` 通过 `AsyncClient.launch_bridge` + `AsyncAgent.prompt(..., client=)` 调用
- 单元测试 mock 同步更新


- 基于 `origin/cursor/cursor-sdk-integration-d454` 继续开发（工作分支 `cursor/sync-cursor-sdk-dc12`）
- `AISettings.effective_cursor_runtime()`：`CURSOR_RUNTIME` 留空且在 `CURSOR_AGENT=1` 时自动使用 `cloud`
- `cursor_transport`：cloud 模式在未配置 `CURSOR_CLOUD_REPOS` 时从 `git remote.origin.url` 推断仓库
- `.env.example`：`CURSOR_RUNTIME` 默认留空并补充说明；`docs/ai-provider.md`、`AGENTS.md` 更新
- 设置 API 返回 `CURSOR_RUNTIME_EFFECTIVE`；补充单元测试

## 2026-07-28

### docs: 新增 docs 目录与详细使用文档

- 新增 `docs/user-guide.md` 用户使用指南
- 新增 `docs/getting-xianyu-cookies.md`（含 F12 手动获取 Cookie 步骤与项目导入方式）
- 新增 `docs/ai-provider.md`（OpenAI 兼容接口与 Cursor SDK 配置、迁移、技术说明）
- README 增加文档索引链接

### feat(ai): 支持 Cursor SDK 作为 AI 提供方

- 新增 `AI_PROVIDER` 配置，支持 `openai`（默认）与 `cursor`
- 新增 `src/infrastructure/external/cursor_transport.py`，通过 Cursor Python SDK 的 `AsyncAgent.prompt()` 完成文本/图片分析
- `AIClient`、`ai_handler`、设置 API 与 Web UI 已接入 Cursor 配置项
- 依赖新增 `cursor-sdk`
