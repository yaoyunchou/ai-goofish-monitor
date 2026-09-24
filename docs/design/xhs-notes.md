# 小红书笔记

> **对应 PRD**：[小红书笔记](../prd/xhs-notes.md)

商品公开页仍然不登录、快照只追加。笔记必须登录，上海日历日一天一行，同日覆盖。

## 1. 菜单和分流

侧栏「小红书」在商品看板下面加「笔记」，路由 `/xhs/notes`。另外：

- `/xhs/notes/add` 添加笔记
- `/xhs/notes/settings` 定时，以及选用哪个小红书账号

商品添加若是笔记链接，不写入 `xhs_products`，返回「这是笔记，请到笔记菜单添加」。识别：

- `xiaohongshu.com/discovery/item/{id}`
- `xiaohongshu.com/explore/{id}`
- 短链解析后的最终地址落在上面两类

失败列表里已经存在的笔记不自动搬迁。

## 2. 表

### `xhs_notes`

`id` 笔记 ID；`source_url`；`title`；`author_name`；`cover_url`；`account_id` 可空，空则用笔记设置里的账号；`active` 默认 TRUE；`last_error`；`last_status` 为 `ok` / `failed` / `login_required`；`created_at` / `updated_at`。

### `xhs_note_daily`

对齐闲鱼日指标。`note_id` 引用笔记，删除笔记时级联删除。`snapshot_day` 是上海时区的日期。`liked_count`、`collected_count`、`comment_count`、`view_count` 都可空。`captured_at` 必填。

`UNIQUE (note_id, snapshot_day)`。同一天再采走 `ON CONFLICT DO UPDATE`。本次没解析到的字段用 `COALESCE(新值, 旧值)`，不把当天已有值覆盖成空。页面没有浏览数就保持空，不写成 0。

列表取最近一个有数据的 `snapshot_day`，以及相对前一天的差值。没有前一天，差值是空，界面显示「—」。

### `xhs_note_schedule`

单行，`id` 固定 1。`cron` 默认 `0 9 * * *`。`enabled` 默认 FALSE。`account_id` 可空。调度 job id 是 `xhs_note_monitor`。`reload_jobs` 只删 `task_*`，不会卸掉它。设置页频率只有每天、每周、每月，不提供每小时。

## 3. 采集

渠道名 `xhs_note`。打开笔记页时，把选定账号文件作为 Playwright `storage_state`。不读闲鱼 `state.json`，也不把这份登录态传给商品公开页。

没有可用的 `xhs` 账号，或文件不存在：本轮不打开浏览器，全部笔记记 `login_required`，`last_error` 为「没有可用的小红书登录」。

页面要求登录或登录已失效：停本轮，账号行写入 `last_error`。笔记之间串行，间隔 3 秒，不做成可调项。

手动「采集全部 / 单条采集」与定时共用 `xhs_note`。本渠道正忙时手动立刻返回「该渠道正在采集」。

## 4. 文件

| 路径 | 动作 |
|------|------|
| `src/domain/xhs_note_parse.py` | 笔记链接与计数字段 |
| `src/xhs_note_collector.py` | 带登录态的浏览器 |
| `src/services/xhs_note_storage.py` | 表读写与同日覆盖 |
| `src/api/routes/xhs_notes.py` | 列表、添加、采集、设置 |
| `src/services/scheduler_service.py` | `xhs_note_monitor` |
| `web-ui/src/views/xhs/XhsNotesView.vue` | 列表与差值 |
