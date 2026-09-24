# 小红书公开商品监控

> **口径**：累计已售的高水位差值，与 hsld `analytics.high_water` 一致。  
> **对照**：[metric-delta-comparison.md](./metric-delta-comparison.md)  
> **闲鱼想要/浏览**：本期不改。

## 1. 变化怎么算

时间一律 `Asia/Shanghai`。

- 高水位（截至 T）= `captured_at <= T` 且 `sold` 非空的最大值。更小的新读数不拉低水位。
- 今日 = 现在的高水位 − 今日 00:00 的高水位。
- 昨日 = 今日 00:00 − 昨日 00:00。00:00 这条只做分界。
- 上小时 = 当前整点高水位 − 上一整点高水位。
- 起点没有快照：增量为空。若区间内已有第一条真实快照，用它做基线，并标 `incomplete=true`（口径不完整）。
- 模糊金额 = 增量 × 该区间内最近一次非空价格。界面标明试算，不是成交额。
- 快照只插入，禁止按日或按整点覆盖。

批量高水位用一条 `GROUP BY product_id` 的 `MAX(sold)`，看板不按商品逐条查询。

## 2. 表

- `xhs_shops`：用户归类的店铺，店名唯一。
- `xhs_products`：商品 ID、链接、标题、页面店名 `shop_name`、归属 `shop_id`、分类、标记、主图、最近价格、最近错误。手选店铺不被页面店名改掉；还没归店且页面有店名时，按店名归入同名店铺。
- `xhs_snapshots`：每次采集一行（`captured_at`、`sold`、`price`）。
- `xhs_schedule`：单行 Cron，默认关闭，表达式 `0 * * * *`（每小时整点，北京时间）。看板上选间隔，或每天、每周、每月的时间，前端再转成 Cron。每周用 `mon`–`sun`（调度器里 0 是周一）。每月 29–31 号在没有这一天的月份会跳过。

建表：`supabase/migrations/20260922000000_xhs_monitor.sql`、`20260922160000_xhs_shops.sql`，并写入 `ensure_incremental_schema`。

店铺今日 / 昨日 / 上小时是店内商品增量相加。缺基线的商品不计入，也不写成 0。有任一计入的增量口径不完整时，整店标不完整。累计已售是监控商品高水位合计，不是店铺真实总销量。

添加在独立页 `/xhs/add`：每行一个链接或商品 ID，同一店铺、分类和标记套用到这一批。也可以用 `.xlsx` 模板，表头为商品链接、店铺、分类、标记。空行跳过。已在监控里的商品，空格子不覆盖。单次最多 500 行。短链遇到公开页 461 时停止后续短链。

商品看板只看还在监控、最近一次没失败也没下架的商品。临时失败在 `/xhs/failed`，忽略后回到看板。页面出现「已下架 / 商品不存在 / 商品已失效 / 违规」时记为下架，进 `/xhs/delisted`，保留快照，后续采集跳过。定时在 `/xhs/settings`。

## 3. 模块

| 职责 | 路径 |
|------|------|
| 高水位与区间 | `src/domain/xhs_analytics.py` |
| 链接解析、公开页字段 | `src/domain/xhs_parse.py` |
| 读写 | `src/services/xhs_storage.py` |
| 公开页采集（浏览器渲染，不带 Cookie） | `src/xhs_collector.py` |
| API | `src/api/routes/xhs.py` |
| 定时 | `SchedulerService.reload_xhs_job`，job id `xhs_monitor` |

`reload_jobs` 只删除 `task_*`。`xhs_monitor` 与卖家订阅一样在 `reload_jobs` 之前挂上，`misfire_grace_time=3600`。

主图经 `GET /api/xhs/cover` 代理，只允许小红书图床域名。

公开页由浏览器打开并等页面画出已售后解析，浏览器不走本机代理。HTTP 461，或页面要求登录且解析不到已售：写入 `last_error`，本轮后续商品不再请求。不使用登录态。
