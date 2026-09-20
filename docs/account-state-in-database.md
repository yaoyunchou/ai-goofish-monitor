# 闲鱼登录态（state/）存入 PostgreSQL

## 结论

**可以放进数据库**，而且放进 Postgres 后就能和任务、结果一样，通过 `REMOTE_DATABASE_URL` / 双向同步脚本在本地与 Supabase 之间对齐。

**当前版本尚未实现**：运行时仍只认磁盘上的 `state/<name>.json`（见 `src/api/routes/accounts.py`、`src/rotation.load_state_files`、`src/scraper` 读文件路径）。把 `state/` 拷到本机只是文件同步，**不会**自动进库。

---

## 为什么现在还在文件里

| 原因 | 说明 |
|------|------|
| 历史设计 | Playwright 原生支持 `storage_state` 文件路径 |
| Docker | `docker-compose.yaml` 直接挂载 `./state` |
| 敏感数据 | Cookie 不宜进 Git；文件 + `.gitignore` 简单 |

爬虫侧已支持 **内存 dict** 作为 `storage_state`（`scraper.py` 读取 JSON 后 `storage_state=snapshot_data`），因此技术上不必长期保留文件，只需在启动浏览器前从 DB 取出 JSON。

---

## 建议表结构（待 migration）

```sql
CREATE TABLE IF NOT EXISTS xianyu_account_states (
    name TEXT PRIMARY KEY,              -- 与现账号名一致，如 xy699909515578
    content_json JSONB NOT NULL,        -- 扩展导出的完整 JSON（含 cookies / env / headers）
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    note TEXT
);

COMMENT ON TABLE xianyu_account_states IS '闲鱼多账号登录态；替代或镜像 state/*.json';
```

可选扩展：

- `content_hash TEXT`：检测变更、避免无意义写入  
- **不要**对 `anon` 开放 RLS 策略（与现有业务表相同，仅服务端 `DATABASE_URL` 访问）

`tasks.account_state_file` 可逐步改为：

- `state/acc.json`（兼容旧值），或  
- `db:账号名` / 仅 `账号名`，由服务层解析为 DB 记录  

---

## 改造范围（实现「进库且能跑爬虫」时）

1. **Migration**：新建 `xianyu_account_states`  
2. **导入**：`state/*.json` → `INSERT ... ON CONFLICT (name) DO UPDATE`（一次性脚本）  
3. **`/api/accounts`**：CRUD 读写表，可选启动时 `EXPORT_STATE_TO_DISK=true` 写回文件兼容旧爬虫  
4. **`rotation` / `scraper`**：账号池从 DB 列名加载；`forced_account` 改为按 `name` 取 JSON，写临时文件或直传 dict（推荐 dict，与现逻辑一致）  
5. **同步**：把 `xianyu_account_states` 加入 `TABLE_ORDER`（在 `tasks` 之前或之后均可，无 FK）  
6. **安全**：备份与权限与 `.env` 同级；日志禁止打印 `content_json`

---

## 过渡方案（不改代码前）

若只想「备份到库里」、爬虫仍用文件：

- 用运维脚本把 JSON 写入 `xianyu_account_states`（表需先 migration）  
- 定时从 DB `COPY` 回 `state/`（或仅部署时导出）

这**不能**替代 Web UI 账号管理，除非接上第 3、4 步。

---

## 与 `package_account_state` 的关系

| 方式 | 适用 |
|------|------|
| `scripts/package_account_state.py` | 机器之间拷 `state/`，不进库 |
| 本文 DB 方案 | 多环境、Supabase 与本地对齐、少挂卷 |

---

## 变更记录

| 日期 | 说明 |
|------|------|
| 2026-08-05 | 初版：可行性、表设计与改造清单 |
