# 账号按渠道分开

> **对应 PRD**：[账号按渠道分开](../prd/account-channels.md)

Cookie 正文继续放文件。数据库只存索引和渠道。

## 1. 表 `monitor_accounts`

写在 `ensure_incremental_schema`，并加 `supabase/migrations/`。

| 列 | 说明 |
|----|------|
| `id` | BIGSERIAL 主键 |
| `channel` | `goofish` 或 `xhs` |
| `name` | 同一渠道内唯一。字母、数字、下划线、短横线，最长 50 |
| `state_path` | 相对 `state/` 的文件名，全局唯一 |
| `enabled` | 默认 TRUE。停用的账号不能被笔记定时选中 |
| `last_checked_at` | 可空。笔记采集用过之后更新 |
| `last_error` | 可空。登录失效、文件缺失写在这里 |
| `created_at` / `updated_at` | TIMESTAMPTZ |

约束：`UNIQUE (channel, name)`，`UNIQUE (state_path)`。

闲鱼文件仍是 `state/{name}.json`，`state_path` 为 `{name}.json`。小红书文件是 `state/xhs/{name}.json`，`state_path` 为 `xhs/{name}.json`。

启动或列出账号时扫描 `state/*.json`（不含子目录）。没有登记的补一行 `channel=goofish`。不移动、不改写这些文件。

## 2. 接口

`GET /api/accounts?channel=goofish|xhs`。不传则返回全部，每行带 `channel`。

新建、修改带 `channel`。缺省新建是 `goofish`，避免现有「用这个账号建任务」被改坏。删除同时删文件和表行。

闲鱼任务选择账号时请求 `channel=goofish`。笔记设置和手动采集只列出 `enabled=true` 的 `xhs`。

## 3. 文件

| 路径 | 动作 |
|------|------|
| `src/infrastructure/persistence/db_connection.py` | 建表 |
| `src/services/monitor_accounts.py` | 登记、查询、停用 |
| `src/api/routes/accounts.py` | 渠道字段 |
| `web-ui/src/views/AccountsView.vue` | 筛选与新建时选择渠道 |
| `web-ui/src/views/TasksView.vue` | 只拉闲鱼账号 |
