# 运行时文件同步（登录态 / 账号 / 配置）

PostgreSQL 同步（见 [database-bidirectional-sync.md](./database-bidirectional-sync.md)）**只覆盖 6 张业务表**，不包含下列「用户信息」相关资源。若本地 **闲鱼账号管理** 为空、爬虫提示未登录、或 Web 管理密码与线上一致，需要单独同步本节内容。

---

## 1. 什么算「用户信息」、存在哪里

| 类型 | 存储位置 | 是否在 Supabase 库里 | 本地现状常见症状 |
|------|-----------|----------------------|------------------|
| **闲鱼多账号登录态** | `state/<账号名>.json`（`ACCOUNT_STATE_DIR`，默认 `state`） | 否 | 「闲鱼账号管理」列表为空 |
| **默认登录态（旧）** | 项目根目录 `xianyu_state.json` | 否 | 部分旧文档/接口仍引用 |
| **Web 管理后台账号** | `.env` 的 `WEB_USERNAME` / `WEB_PASSWORD` | 否 | 能用 admin 登录但密码与线上不同 |
| **任务绑定的账号路径** | `tasks.account_state_file`（库内字段） | 是（已随 DB 同步） | 字段有值但本地无对应 JSON 文件仍会失败 |
| **商品结果里的卖家资料** | `result_items.raw_json` → `卖家信息` | 是（已随 DB 同步） | 若仍空白，检查是否未同步 `result_items` 或该条本身无卖家块 |
| **Supabase Auth `auth.users`** | Supabase 内置 | 与本项目 Web 登录无关 | 本项目不用 Supabase 做后台登录 |

线上 Docker 部署时，`docker-compose.yaml` 会把宿主机 `./state` 挂载进容器：

```yaml
volumes:
  - ./state:/app/state
```

因此 **线上真实 Cookie 在跑应用的那台机器上的 `state/` 目录**，不在 Supabase 数据库里。

若希望登录态随 Postgres 一起在本地/线上同步，需要单独做 **入库方案**，见 [account-state-in-database.md](./account-state-in-database.md)（当前代码仍只读文件）。

---

## 2. 推荐：从线上服务器拷贝 `state/`

在**部署了线上应用**的机器上打包（Linux 示例）：

```bash
cd /path/to/ai-goofish-monitor
tar -czf state-backup.tar.gz state/
```

拷到本机后（Windows PowerShell 示例）：

```powershell
cd C:\Users\yao\Desktop\work\2026\ai-goofish-monitor
mkdir state -Force
tar -xzf \\path\\to\\state-backup.tar.gz
```

或用 `scp` / WinSCP 直接同步整个 `state` 文件夹到仓库根目录。

完成后重启本地后端，打开 Web UI → **闲鱼账号管理**，应能看到与线上一致的账号列表。

---

## 3. 使用仓库脚本打包 / 恢复（无 SSH 时）

在任意一台**已有** `state/*.json` 的机器上导出：

```bash
python -m scripts.package_account_state export --out state-backup.tar.gz
```

在本机恢复（会覆盖同名文件）：

```bash
python -m scripts.package_account_state import --archive state-backup.tar.gz
```

---

## 4. 无法拿到线上 `state/` 时

1. 用 Chrome 扩展按 [getting-xianyu-cookies.md](./getting-xianyu-cookies.md) 重新导出登录态。  
2. 在本地 Web UI **闲鱼账号管理** 粘贴 JSON 新建账号（名称建议与线上任务里 `account_state_file` 的文件名一致，不含 `.json`）。  
3. 在 **任务** 里将 `account_strategy` / `account_state_file` 与线上一致（库内任务配置若已 DB 同步，通常只需补文件）。

---

## 5. Web 后台登录（非闲鱼）

将线上 `.env` 中的以下项**手动**合并到本地 `.env`（勿提交 Git）：

```env
WEB_USERNAME=...
WEB_PASSWORD=...
```

修改后重启 `python -m src.app`。

---

## 6. 与数据库同步一起做的检查清单

- [ ] `python -m scripts.verify_database` 通过  
- [ ] 本地存在 `state/*.json`，且账号名与任务配置一致  
- [ ] `.env` 中 `WEB_USERNAME` / `WEB_PASSWORD`（如需与线相同）  
- [ ] 可选：`images/`、`jsonl/` 若 UI 要显示历史图片或旧 jsonl 路径  

---

## 7. 变更记录

| 日期 | 说明 |
|------|------|
| 2026-08-05 | 初版：说明用户信息不在 DB 同步范围；state 拷贝与打包脚本 |
