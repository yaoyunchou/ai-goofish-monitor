# 变更日志

## 2026-08-07

### fix(dev): 修复 uvicorn --reload 在 Windows 下日志 ValueError: underlying buffer has been detached

- **问题**：`start_dev.sh` 用 `uvicorn --reload` 时，reloader 通过 multiprocessing spawn 启动子进程，子进程继承了指向已 detach 缓冲的 `StreamHandler`，导致 uvicorn 自身日志（`Started server process`、`Waiting for application startup` 等）每次 emit 都抛 `ValueError: underlying buffer has been detached`，刷屏但不影响服务。
- **第一版修复的不足**：用 `getattr(self.stream, "closed", False)` 判断流是否可用，但访问 `TextIOWrapper.closed` 本身就会触发已 detach 的缓冲而抛 `ValueError`，而 `getattr` 的默认值只兜底 `AttributeError`，于是 guard 自身再次崩溃。
- **最终修改**：`src/app.py` 顶部新增 `_RobustStreamHandler` 与 `_install_robust_logging()`：
  - `_is_stream_broken` 用 `try/except (ValueError, OSError)` 包住 `stream.closed` 访问，正确识别坏流。
  - `_resolve_stream` 沿用原方向（stdout/stderr），坏掉则退回另一边，两边都坏返回 `None` 丢弃该条日志，绝不抛错。
  - `emit` 先确保流可用，再 `super().emit()`，仍捕获 `ValueError/OSError` 并重置流。
  - 替换 root logger 与 `uvicorn`/`uvicorn.error`/`uvicorn.access` 三个 logger 的 handler，关闭 propagate 避免重复输出。

### fix(dev): start_dev.sh 在 MINGW 下 PIP_CMD 变量含空格导致执行失败

- **问题**：`PIP_CMD="$VENV_PYTHON -m pip"` 后 `"$PIP_CMD" install ...` 把整串当作单一可执行路径，bash 报 `No such file or directory`。
- **修改**：改为数组 `PIP_CMD=("$VENV_PYTHON" -m pip)` 并用 `"${PIP_CMD[@]}" install` 调用，正确分词。

### feat(sellers): 关注卖家功能完整实现（规范化表 + 服务 + API + 前端）

- **目标**：实现「关注卖家」功能——从收录详情页关注卖家、按 cron 定时拉取卖家商品、按热度排序查看，并完成 MTOP detail 数据的规范化拆表。
- **数据库迁移**：
  - `supabase/migrations/20260807000000_goofish_normalized_schema.sql`：创建 11 张 `goofish_` 前缀规范化表（`goofish_sellers`、`goofish_items`、`goofish_item_skus`、`goofish_item_images`、`goofish_item_labels`、`goofish_item_tags`、`goofish_categories`、`goofish_seller_tags`、`goofish_seller_other_items`、`goofish_item_details`、`goofish_item_track_params`），含主键/外键/raw_json 全量保留。
  - `supabase/migrations/20260807010000_followed_sellers.sql`：创建业务表 `followed_sellers`（关注关系 + per-seller cron）与 `seller_item_snapshots`（商品快照，按 seller+item+fetched_at 唯一）。
- **后端**：
  - 新增 `src/services/detail_normalizer.py`：将 MTOP `detail_data` 拆分写入 11 张规范化表，单事务提交，失败不影响 `collected_items` 主流程。
  - `src/services/collection_service.py`：`refresh_collection_skus` 完成后在 `detail_data` 存在时调用 `normalize_and_save_detail`。
  - 新增 `src/services/seller_service.py`：关注/取消关注/列表/详情/刷新商品（Playwright 捕获 `mtop.idle.web.xyh.item.list` 写快照 + 对前 N 个商品调 `mtop.taobao.idle.pc.detail` 补 want/browse/sold 热度），支持 per-seller cron 更新与批量刷新。
  - 新增 `src/api/routes/sellers.py`：`GET/POST/DELETE /api/sellers`、`GET /api/sellers/{id}`、`POST /api/sellers/{id}/refresh`、`POST /api/sellers/refresh-all`、`PUT /api/sellers/{id}/cron`，并在 `src/app.py` 注册路由。
  - `src/services/scheduler_service.py`：`reload_jobs` 末尾调用 `_load_seller_jobs`，按每个关注卖家的 cron 注册 `seller_{id}` 定时任务，触发 `_run_seller_refresh`。
  - `src/parsers.py`：`_parse_user_items_data` 增加 `wantCnt/browseCnt/collectCnt/soldCnt` 字段解析。
- **前端**：
  - 新增 `web-ui/src/api/sellers.ts`：API 封装 + `FollowedSeller`/`SellerItem` 类型。
  - `web-ui/src/router/index.ts`：新增 `/sellers`、`/sellers/:sellerId` 路由。
  - `web-ui/src/components/layout/TheSidebar.vue`：侧边栏新增「关注卖家」导航（`UserCheck` 图标）。
  - 新增 `web-ui/src/views/FollowedSellersView.vue`：关注卖家列表卡片（头像/城市/在售/已售/好评/最近拉取/cron/刷新/取消关注）。
  - 新增 `web-ui/src/views/SellerDetailView.vue`：卖家详情页（卖家信息卡 + 按想要数/浏览数/已售数/价格排序的商品网格）。
  - `web-ui/src/views/CollectionDetailView.vue`：卖家信息卡新增「关注卖家」按钮，加载时检查关注状态，支持关注/取消关注切换。
  - i18n：`zh-CN.ts`/`zh-CN-extra.ts`/`en-US.ts`/`en-US-extra.ts` 新增 `sidebar.sellers`、`routes.sellers/sellerDetail`、`sellers.*` 文案。
- **验证**：前端 `npm run build` 通过；`test_idle_mtop_client.py` 3/3 通过；`test_item_detail_parser.py` 中 2 个失败为前序 SKU 解析改动遗留，本次未触碰。

### feat(dev): 新增 start_dev.sh（uvicorn reload + Vite HMR）

- 新增 `start_dev.sh`：`.venv` 装依赖后并行启动 `uvicorn --reload` 与 `npm run dev`，Ctrl+C 一并退出。
- `web-ui/vite.config.ts` 从根目录 `.env` 读取 `SERVER_PORT` 配置 API/WebSocket 代理。
- README 区分 `start.sh`（生产式 build）与 `start_dev.sh`（日常开发）。

### fix(docker): 官方镜像不含本地前端/收录 API，增加 local 构建 compose

- **说明**：`docker-compose.local.yaml` 仅用于**服务器跑当前仓库源码**；日常开发应 **Postgres 用 `docker-compose.dev.yml`，应用在宿主机 `uvicorn --reload` + `npm run dev`**（README 已补充）。

### fix(docker): 端口映射与 SERVER_PORT 对齐

- **问题**：`.env` 中 `SERVER_PORT=7000` 时，容器内监听 7000，但 `docker-compose.yaml` 固定 `8000:8000`，导致 Web 无法访问。
- **修改**：`docker-compose.yaml` 使用 `${SERVER_PORT:-8000}:${SERVER_PORT:-8000}`，并增加 `host.docker.internal` 便于容器访问宿主机 Postgres。
- **运维**：数据库请用 `docker compose -f docker-compose.dev.yml up -d`（含 `POSTGRES_PASSWORD`），勿单独 `docker run postgres` 无密码。

## 2026-08-06

### feat(collections): 收录详情页全量展示 MTOP detail 所有字段并入库结构化列

- **目标**：用户要求完整数据全部入库、不遗漏，详情页展示 MTOP `mtop.taobao.idle.pc.detail` 返回的所有有用字段。
- **迁移**：`supabase/migrations/20260806240000_collected_items_full_columns.sql`
  - `collected_items` 新增 18 个结构化列：`title`、`sold_price`、`original_price`、`want_cnt`、`browse_cnt`、`collect_cnt`、`sold_cnt`、`quantity_cnt`、`category_id`、`main_pic_url`、`image_count`、`sku_count`、`seller_name`、`seller_city`、`seller_sold_cnt`、`seller_item_count`、`seller_good_rate`、`seller_register_days`。
  - 新增索引：`title`、`sold_price`、`category_id`、`seller_name`、`want_cnt DESC`。
  - 完整 `detail_data` 仍全量保留在 `sku_json.detail_data` JSONB 中。
- **后端**：`src/services/collection_service.py`
  - `refresh_collection_skus` 从 `detail_data.itemDO`/`sellerDO`/`trackParams` 提取所有结构化字段写入新列，日志打印 `labels/tags/seller/sku/img` 计数。
  - UPDATE SQL 扩展为 25 列写入。
- **前端**：`web-ui/src/views/CollectionDetailView.vue` 新增展示区块：
  - **SKU 规格列表**（`skuList`/`idleItemSkuList`）：表格展示 SKU 图、规格属性、价格（`priceInCent`/100）、库存、SKU ID。
  - **分享数据**（`shareData.shareInfoJsonString`）：解析 JSON 展示分享文案与全部图片。
  - **跟踪参数**（`trackParams`）：卖家ID、分类ID、频道分类、买家ID、商品ID、主图、勋章。
  - **买家信息**（`buyerDO`）：买家ID、店铺用户、已收藏、超级关注、关注状态。
  - **配置信息**（`configInfo`）：全部配置项标签展示。
  - **卖家增强**：签名（`signature`）、24h回复率精确值（`replyIn24hRatioDouble`）、等级标签图片（`levelTags`）、闲鱼信用徽章（`idleFishCreditTag`）。
  - **卖家其他在售**：改为可点击链接跳转闲鱼商品页。
  - **完整原始 JSON**：底部 `<details>` 折叠展示 `detail_data` 全量 JSON，确保不漏任何字段。
- **类型**：`web-ui/src/types/collection.d.ts` 补充 `skuList`/`idleItemSkuList`/`shareData`/`richTextDesc`/`bargained`/`itemType`/`secuGuide`/`spuBottomBarItem`/`trackParams`(顶层)/`buyerDO`/`configInfo`/`serverTime`；`sellerDO` 补充 `signature`/`replyIn24hRatioDouble`/`levelTags`/`idleFishCreditTag`/`sellerItems.link`/`identityTags.iconUrl,link`。
- **验证**：迁移已应用；`npm run build` 通过；collection #3 已刷新回填新列。

### feat(collections): 收录详情页全量展示 itemDO/sellerDO 所有字段

- **问题**：详情页遗漏大量字段未展示（`wantCntUnit`、`originalPrice`、`resellDiscount`、`recommendTagList`、`gmtCreate`、`guideProdParamInfo`、`portraitUrl`、`xianyuSummary`、`registerTime` 等），且头像字段名错误（`avatarUrl` 应为 `portraitUrl`）。
- **前端**：`web-ui/src/views/CollectionDetailView.vue`
  - **价格区**：新增原价（`originalPrice`，划线显示）、转卖折扣（`resellDiscount`）、转卖标签（`descTag`）、状态标签（`itemStatusStr`）。
  - **统计栏**：从 4 格扩展到 6 格，新增已售（`soldCnt`）、发布日期（`gmtCreate` 格式化）；想要数附带 `wantCntUnit`（"人想要"）。
  - **标签区**：拆分为三组并标注来源——商品分类（`itemLabelExtList`+`cpvLabels`）、通用标签（`commonTags`）、推荐标签（`recommendTagList`）。
  - **基本信息**：新增商品ID（`itemId`）、分类ID（`categoryId`）、分类路径（`itemCatDTO`）。
  - **SKU 参数**：新增 `guideProdParamInfo` 卡片，展示 SKU 名称、价格、标题。
  - **卖家信息**：头像改用 `portraitUrl`（兼容 `avatarUrl` 兜底）；头部展示头像+昵称+闲鱼简介（`xianyuSummary`）+个人主页链接；新增发货城市（`publishCity`）、30天平均回复（`avgReply30dLong`）、注册时间（`registerTime` 格式化）。
  - **个人主页链接**：`pageUserId` 为空时回退 `userId`/`sellerId`。
- **类型**：`web-ui/src/types/collection.d.ts` 的 `itemDO` 补充 `wantCntUnit`、`descTag`、`resellDiscount`、`categoryId`、`recommendTagList`、`descRelativeTags`、`guideProdParamInfo`、`trackParams`；`sellerDO` 补充 `portraitUrl`、`xianyuSummary`、`registerTime`、`avgReply30dLong`、`idleFishCreditTag`。
- **验证**：`npm run build` 通过；collection #3 已通过脚本刷新，`detail_data` 已入库（Playwright 兜底捕获 MTOP 详情接口）。

### feat(collections): 商品分类标签 itemLabelExtList/cpvLabels/commonTags 入库为结构化列

- **问题**：`itemLabelExtList`（商品分类）、`cpvLabels`、`commonTags` 此前仅埋在 `sku_json` JSONB 内，无法直接查询/筛选/聚合。
- **迁移**：`supabase/migrations/20260806230000_collected_items_labels.sql`
  - `collected_items` 新增 `item_labels JSONB`（去重后的 `[{label,value}]`）、`common_tags JSONB`（`[string]`）、`seller_id TEXT`。
  - 新增 GIN 索引 `idx_collected_items_item_labels` / `idx_collected_items_common_tags`，支持 `@>` 包含查询；`seller_id` 普通索引。
- **后端**：`src/services/collection_service.py`
  - `refresh_collection_skus` 在写回 SKU 后，从 `detail_data.itemDO` 提取 `itemLabelExtList` + `cpvLabels`（按 `label:value` 去重）写入 `item_labels`，`commonTags` 写入 `common_tags`，`sellerDO.pageUserId/userId/sellerId` 写入 `seller_id`，并打印提取日志。
  - `_row_to_collection` 暴露 `item_labels` / `common_tags` / `seller_id` 给前端（兼容旧库无列场景，用 `"item_labels" in row.keys()` 守卫）。
- **前端**：`web-ui/src/views/CollectionDetailView.vue`
  - `labels` / `tags` 计算属性增加兜底：`detail_data` 为空时回退到 DB 结构化列 `item_labels` / `common_tags`。
- **类型**：`web-ui/src/types/collection.d.ts` 的 `CollectionItem` 补充 `item_labels`、`common_tags`、`seller_id`。
- **验证**：迁移已应用；`npm run build` 通过；后端 import 正常。旧记录需重新拉取 SKU 才会回填新列。

### feat(collections): 收录详情页卖家信息补全用户ID与个人主页链接

- **问题**：`sellerDO` 中的 `pageUserId`/`userId` 等关键字段未展示，且无法跳转到卖家个人主页。
- **前端**：`web-ui/src/views/CollectionDetailView.vue`
  - 卖家信息卡片新增 `用户ID`、`主页ID`（`pageUserId`）、`卖家ID`、`头像`（`avatarUrl`）字段，ID 之间互不相同才显示，避免重复。
  - 卡片标题右侧新增「查看个人主页」外链，URL 为 `https://www.goofish.com/personal?userId={pageUserId||userId||sellerId}`，新标签页打开。
  - 卡片显示条件由 `sellerDO.sellerId` 放宽为 `sellerId || userId || pageUserId`，兼容不同接口返回。
- **类型**：`web-ui/src/types/collection.d.ts` 的 `sellerDO` 补充 `userId`、`pageUserId`、`avatarUrl` 字段。
- **验证**：`npm run build` 通过。

### fix(collections): 收录详情页补全图片/标签/卖家信息与原始数据兜底

- **问题**：收录 #3 详情页图片/标签/卖家全空，原因是该条目由 Playwright 兜底路径抓取，未存储 `detail_data`；同时 `itemLabelExtList` 与 `cpvLabels` 存在重复字段（成色、保质期）导致「名字重复两遍」。
- **后端**：`src/services/item_sku_fetch_service.py` Playwright 兜底路径从捕获响应中提取 `itemDO`/`sellerDO`，调用 `_build_sku_result` 时透传 `detail_data` 与 `item_id`，与 MTOP 路径保持一致。
- **前端**：`web-ui/src/views/CollectionDetailView.vue`
  - `labels` 计算属性对 `itemLabelExtList` + `cpvLabels` 按 `label:value` 去重，消除重复展示。
  - `images` 计算属性增加兜底：`detail_data.itemDO.imageInfos` 为空时回退到 `record.商品信息.商品图片列表` / `商品主图链接`。
  - 新增「AI 分析（爬取时）」卡片：展示 `record.ai_analysis` 的 `is_recommended`、`value_score`、`reason`。
  - 新增「原始爬取数据」卡片：展示 `record.商品信息` / `record.卖家信息` 的成色、发布时间、卖家信用、实名认证、好评率、城市等字段，弥补 `detail_data` 缺失场景。
- **验证**：`npm run build` 通过；后端需重新「重新拉取 SKU」才能让 Playwright 路径回填 `detail_data`。

### feat(detail): MTOP 直调 `mtop.taobao.idle.pc.detail` 拉取详情与 SKU

- 新增 `src/services/idle_mtop_client.py`：从 `state/*.json` 读取 Cookie，按 H5 规则计算 `sign` 并 POST `data={"itemId":"..."}`（与浏览器 curl 一致）
- `item_sku_fetch_service` 优先走 MTOP，失败再 Playwright 监听；`sku_json` 增加 `fetch_method`、`detail_data`（完整 `data` 段，含 `itemDO` / `sellerDO`）
- `item_detail_parser`：识别 `priceInCent`（8700→¥87）、`itemDO.skuList`/`idleItemSkuList` 去重、支持直接传入 `itemDO` 片段
- 新增 `scripts/debug_idle_detail.py`：MTOP 详情调试脚本（dry-run 签名 / 真实调用 / 本地解析 / 保存原始 JSON）
- `idle_mtop_client` 支持 `IDLE_MTOP_VERIFY_SSL` 环境变量与 `verify` 参数，调试脚本 `--insecure` 跳过 SSL 校验（Windows CA 不全时用）

### fix(scripts): start.sh 在 Windows/Git Bash 下误报 python3 缺失

- MINGW/MSYS 环境无 `python3` 命令，改用 `PYTHON_CMD` 变量：Windows 下优先 `python`，其次 `py`
- 脚本主体的依赖检查、pip 安装、启动后端均改用 `$PYTHON_CMD` / `$PIP_CMD`
- 修复 CRLF 换行导致 bash 报 `$'\r': command not found`

### chore(dev): 项目启用 .venv 虚拟环境

- `start.sh` 自动创建并切换到 `.venv`：首次运行用系统 Python 建 venv，后续所有 pip install / 启动均走 venv
- `.gitignore` 新增 `.venv/`
- 已在 `.venv` 安装 `requirements.txt` 依赖 + Playwright Chromium
- 清理全局 Python 之前误装的 fastapi/playwright/uvicorn/httpx/requests
- README「开发者开发」章节更新：一键启动说明 .venv、手动启动/测试改用 `.venv` 路径
- 修复 `.venv` greenlet 3.5.4 DLL 加载失败：固定 `greenlet==3.1.1`（与 Python 3.12.9/win_amd6464 兼容）
- `.vscode/launch.json` 新增调试配置：后端服务、爬虫 CLI、MTOP 详情调试、当前文件、pytest，均使用 `.venv` 的 python
- 端口 8000 被占用，`.env` / `start.sh` / `launch.json` 改为 7000

### feat(web-ui): 新增「收录商品」菜单与列表页

- 侧边栏新增「收录商品」菜单（Bookmark 图标），位于「结果查看」与「运行日志」之间
- 新增 `CollectionsView.vue`：卡片网格展示所有收录商品，含标题、价格、SKU 状态徽标、规格数、收录时间
- 支持点击卡片进入收录详情、取消收录、打开闲鱼链接
- 路由 `/collections` → `CollectionsView`；收录详情「返回」改为回到收录列表
- 中英文 i18n 补全 `sidebar.collections` / `routes.collections` / `collections.list.*`

### feat(sku): 收录 SKU 拉取全链路日志

- `idle_mtop_client`：MTOP 调用前打印 api/data/verify，响应后打印 HTTP 状态码 + ret 文本
- `item_sku_fetch_service`：MTOP 路径打印 itemId/link/title/soldPrice/skuList 条数；失败时打印异常类型和原因再切 Playwright；Playwright 每捕获一条接口都打印 URL
- `collection_service`：收录和刷新 SKU 打印 collection_id/link/title/最终状态/method/SKU 数量/错误信息

### feat(db): 登录态存入 PostgreSQL，全链路改读 DB

- 新增 migration `20260806220000_xianyu_account_states.sql`：`xianyu_account_states(name, content_json, updated_at, note)`
- 新增 `src/services/account_state_store.py`：统一账号态存取（DB 优先，文件兜底，自动导入）
- `idle_mtop_client`：`load_state_cookies` / `resolve_state_file` 改读 DB
- `item_sku_fetch_service`：Playwright 兜底用 DB 取 `storage_state` dict，不再依赖文件路径
- `rotation.load_state_files`：优先从 DB 列账号名，文件目录扫描兜底
- `scraper._run_scrape_attempt`：`get_account_state` 替代 `open(state_file)`
- `accounts.py` API：CRUD 改为 DB 读写（`save_account_state` / `delete_account_state`）
- `login_state.py` API：保存时 DB + 文件双写
- 新增 `scripts/import_account_states.py`：建表 + 导入 `state/*.json` 到 DB
- 已导入 `user_874979280` 到 `xianyu_account_states`，验证 cookies(54) + `_m_h5_tk` 均正常

### feat(web-ui): 收录详情页展示完整商品数据

- `collection_service._row_to_collection` 新增返回 `detail_data`（MTOP 完整 `data` 段）
- `collection.d.ts` 新增 `CollectionDetailData` 类型（`itemDO` / `sellerDO` 全字段）
- `CollectionDetailView.vue` 重写：图片画廊、商品信息卡片（想要/浏览/收藏/库存）、标签（成色/保质期/分类）、包邮标签、商品描述、卖家信息（昵称/城市/已售/回复率/好评/芝麻认证）、卖家其他在售商品网格、SKU 表格（含库存列）
- 单测校验签名向量与链接解析 `itemId`

## 2026-08-05

### chore(ops): 线上 Supabase → 本地 Postgres 数据同步

- 通过 MCP 导出 + `data/db_sync_snapshot` 快照，将业务表写入本机 `goofish`（`tasks` 2、`result_items` 10、`price_snapshots` 26 等，与线上一致）
- 修复 `sync_postgres_remote_to_local._insert_batch`：导入前对 JSONB 列执行 `_adapt_row`，避免 `keyword_rules_json` 写入失败
- 增强 `mcp_extract_rows`（`payload` / `row_to_json` 格式）；新增 `decode_mcp_b64_export.py`、`import_table_snapshot.py`（单表覆盖）
- 后续一键同步：在 `.env` 配置 `REMOTE_DATABASE_URL`（Session pooler）后执行 `python -m scripts.sync_postgres_remote_to_local`
- 新增文档 `docs/database-bidirectional-sync.md`：本地 ↔ Supabase 双向同步范围、冲突策略与分阶段实施计划（实现待办）
- 新增 `docs/sync-runtime-files.md` + `scripts/package_account_state.py`：说明闲鱼账号登录态（`state/`）不在 DB 同步内，支持 tar.gz 导出/导入
- 新增 `docs/account-state-in-database.md`：登录态入库可行性、表结构与改造清单（尚未实现）

### chore(dev): 本地一键 PostgreSQL + 前端构建

- 新增 `docker-compose.dev.yml`：本机 Postgres 16，首次启动自动执行 `supabase/migrations/20260803120000_initial_goofish_schema.sql`
- 从 `.env.example` 生成 `.env`，`DATABASE_URL` 指向 `127.0.0.1:5432/goofish`（与 compose 默认账号一致）
- 完成 `pip install -r requirements.txt`、`playwright install chromium`、`web-ui` 生产构建（产物在根目录 `dist/`）

## 2026-08-04

### chore(ops): 更新账号 user_874979280（蓝小飞鱼）登录态

- 自 Cookie 请求头导入并覆盖 `state/user_874979280.json`（多域名展开）

### fix(scraper): 搜索 resultList 解析与响应选择

- 支持 MTOP `data` 为 JSON 字符串时解包 `resultList`（此前只读 `data.resultList` 对象形式）
- 筛选后优先选用 **非空** 的 initial/final 搜索响应，避免「个人闲置」等把有效首屏数据覆盖为空
- 首屏与筛选均无列表时滚动触发一次搜索 API 重试
- 空列表时输出 `[搜索诊断]`（ret、data_keys、resultList 长度）；`AI_DEBUG_MODE=true` 仍打印完整 JSON
- 个人闲置筛选超时/失败时回退首屏响应，不再直接中断


- `decision_mode=keyword`，搜索词为「天才知音全新儿童故事机早教机智能学习机随身听」
- 匹配规则：`天才知音`、`故事机`（标题命中即关键词推荐，不走 AI 看图）
- 绑定账号 `state/xy699909515578.json`，cron 每 2 小时，`task id=1`

### chore(ops): 刷新闲鱼 Cookie 登录态

- 更新 `state/xy699909515578.json`（多域名 `.goofish.com` / `.taobao.com` 展开，便于 Playwright 携带）
- 任务「机乐堂30w多口充电头」重新绑定 `account_strategy=fixed`
- 验证：搜索页可解析商品列表；此前 02:00 失败为旧 Cookie 跳转登录页

### chore(release): 合并 Postgres-only 与配置修复到 `master`

- 将 `cursor/remove-sqlite-postgres-only-dc12` fast-forward 合入 `origin/master`（含 #6 / #7 对应改动）
- 从仓库删除误提交的 `.env.20260803` / `.env.20260804`，并忽略 `.env.202608*`
- 已关闭重复 PR #9（与 master 实现路径冲突，内容已由 dc12 分支覆盖）

### chore(tasks): 新增监控任务「机乐堂30w多口充电头」

- 通过 API 写入 Supabase `tasks` 表（AI 判定、看图、价格 30–150、cron 每 2 小时）
- 新增 `prompts/机乐堂_30w多口充电头_criteria.txt`

### chore(docs): 全面去除 SQLite 文档与配置残留

- README / README_EN / user-guide / AGENTS / database-supabase-integration 统一为仅 PostgreSQL
- `.env` 示例与备份注释去掉 `DATABASE_DRIVER`、`APP_DATABASE_FILE`
- `storage_names` 重命名为 `LEGACY_SQLITE_MIGRATION_SOURCE`（仅迁移脚本）
- live 测试不再注入 `APP_DATABASE_FILE`
- MySQL 迁移计划文档标注为归档参考

### feat(db): SQLite → Postgres 迁移 CLI + 运行时仅 Postgres

- 新增 `python3 -m scripts.migrate_sqlite_to_postgres`（保留 tasks/result_items 等主键 id）
- 移除运行时 SQLite：`db_connection` 仅连 `DATABASE_URL`；删除 `sqlite_connection` 等
- 测试任务 API 使用 `InMemoryTaskRepository`，不连真实库
- `.env.example` 仅保留 `DATABASE_URL`

### fix(config): 数据库配置与 env_manager 统一（.env 优先于 Secrets）

- `database_config` 的 `DATABASE_DRIVER` / `DATABASE_URL` / `APP_DATABASE_FILE` 改为经 `env_manager.get_value` 解析，与 Web 设置、系统状态一致
- `verify_database` 输出配置来源；密码失败与 IPv6 分开展示提示
- `EnvManager.config_source()` 供运行时诊断
- 测试使用 `data/.pytest-env`，避免仓库 `.env` 干扰
- 本地可保留 `.env` 备份文件，但勿提交 Git（已加入 `.env.202608*` 忽略规则）

## 2026-08-03

### feat(db): DATABASE_DRIVER=postgres（Supabase / psycopg）

- 新增 `database_config`、`db_connection`、`sql_dialect`、`storage_bootstrap`
- 任务/结果/收录/行情读写统一走 `db_connection()`，Postgres 使用 `ON CONFLICT` 方言
- 依赖：`psycopg[binary]>=3.1.18`
- 测试环境强制 `DATABASE_DRIVER=sqlite`
- 验证脚本：`python3 -m scripts.verify_database`

- `docs/database-supabase-integration.md`（项目 wkhatdhgohkpsqkytotz 连接串与 checklist）
- `supabase/migrations/20260803120000_initial_goofish_schema.sql`
- `.env.example` 增加 `DATABASE_DRIVER` / `DATABASE_URL`

### docs: SQLite → MySQL 迁移计划

- 新增 `docs/database-mysql-migration-plan.md`（现状盘点、分阶段 A～E、DDL/测试/风险 checklist）

### feat(scraper): 分析代理增加统一 AI 品类过滤（门禁）

- 新增 `src/services/listing_ai_filter.py` 与 `prompts/listing_ai_filter_system.txt`
- `ItemAnalysisDispatcher` 在关键词/完整 AI 分析前执行过滤，剔除「仅数据线」等非目标品类（`analysis_source=ai_filter`）
- 环境变量 `AI_LISTING_FILTER_ENABLED`（默认 `true`）；任务级可用 `enable_ai_listing_filter` 覆盖
- 购买意图取自任务 `description`（空则回退搜索 `keyword`）；过滤阶段最多下载 2 张图辅助识别

### feat(collections): 收录商品并拉取全量 SKU 价格

- `src/services/collection_service.py`、`item_sku_fetch_service.py`、`parsers/item_detail_parser.py`
- API：`/api/collections`（收录、详情、刷新 SKU）
- 结果列表项附带 `_result_item_id` 字段

## 2026-07-31

### chore(tasks): 机乐堂 30W 任务改为 AI 判定并补充 criteria

- 任务「机乐堂30W充电头」由关键词 OR 模式改为 `decision_mode=ai`，启用看图分析
- 新增 `prompts/机乐堂_30w_充电头_criteria.txt`（品牌一票否决、排除卡斐乐等非机乐堂）
- 结果集 `机乐堂_30w_充电头_full_data.jsonl` 配置展示黑名单关键词，便于结果页过滤误匹配

## 2026-08-04

### chore(ops): 导入闲鱼 Cookie 至账号管理

- 将用户提供的 Cookie 请求头转换为 Playwright `cookies` JSON，写入 `state/xy699909515578.json`（账号名取自 `tracknick`）
- 任务「机乐堂30w多口充电头」已绑定 `account_strategy=fixed` 与上述登录态文件
- 临时导入文件已删除；`state/` 仍在 `.gitignore`，不会进入版本库

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
