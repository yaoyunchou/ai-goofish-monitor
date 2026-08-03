# 闲鱼 Cookie / 登录态获取指南

爬虫需要有效的闲鱼登录态才能搜索商品。本项目将登录态保存为 **JSON 文件**（默认目录 `state/`），并在 Playwright 启动浏览器时加载。

> **推荐方式**：使用 [Chrome 扩展](./getting-xianyu-cookies.md#方式二chrome-扩展推荐) 一键导出完整登录态（Cookie + 浏览器环境 + 请求头），成功率更高。  
> 下文「方式一」适合你想手动从开发者工具复制 Cookie 的场景。

---

## 方式一：Chrome 开发者工具手动获取 Cookie

### 操作步骤

1. 使用 **Chrome 浏览器** 访问闲鱼网页版：[https://www.goofish.com/](https://www.goofish.com/)
2. **登录** 你的闲鱼账号
3. 按 **F12** 打开开发者工具，切换到 **「网络 / Network」** 标签页
4. 在筛选栏选择 **「Fetch/XHR」**
5. **刷新页面**，在请求列表中找到任意一个发往闲鱼接口的请求（通常名称类似 `1.0/?jsv=2.7.2&appKey=...`）
6. 点击该请求，在右侧 **「标头 / Headers」** → **「请求标头 / Request Headers」** 中找到 **`Cookie`** 字段
7. **完整复制** `Cookie` 的值（通常是一长串 `key1=value1; key2=value2; ...`）

### 图示说明

```
① 点击「网络 / Network」
② 点击「Fetch/XHR」
③ 刷新页面后，点击列表中的任意请求
④ 在 Request Headers 中找到 Cookie，复制完整内容
```

### 在本项目中的使用方法

本项目 **不直接使用** 名为 `COOKIES_STR` 的环境变量，而是将登录态保存为 JSON 后供爬虫读取。拿到 Cookie 字符串后，请按下面任一方式导入：

#### 选项 A：通过 Web UI 导入（推荐）

1. 启动项目并打开 Web UI：`http://localhost:8000`
2. 进入 **「闲鱼账号管理」**
3. 若你已有 Chrome 扩展导出的 JSON，直接粘贴保存即可
4. 若你只有原始 Cookie 字符串，需先整理成 Playwright 可识别的 JSON（见下方「Cookie 字符串转 JSON」），再粘贴导入
5. 创建任务时 **绑定该账号**

导入后文件会保存到 `state/<账号名>.json`，例如 `state/acc_1.json`。

#### 选项 B：手动写入文件

将整理好的 JSON 保存为：

```text
state/acc_1.json
```

或在根目录使用默认文件：

```text
xianyu_state.json
```

### Cookie 字符串转 JSON（仅手动复制 Cookie 时需要）

Playwright 需要结构化的 `cookies` 数组，而不是原始 Cookie 请求头字符串。最小可用格式示例：

```json
{
  "cookies": [
    {
      "name": "cookie_name_1",
      "value": "cookie_value_1",
      "domain": ".goofish.com",
      "path": "/"
    },
    {
      "name": "cookie_name_2",
      "value": "cookie_value_2",
      "domain": ".goofish.com",
      "path": "/"
    }
  ]
}
```

将 `Cookie: a=1; b=2; c=3` 拆分为多条 `{name, value}` 记录即可。  
若觉得繁琐，**强烈建议改用 Chrome 扩展**（方式二），可自动导出完整格式。

---

## 方式二：Chrome 扩展（推荐）

扩展会自动采集 Cookie、User-Agent、时区、屏幕参数等，更贴近真实浏览器，反爬成功率更高。

### 安装与使用

1. 安装扩展：[Chrome 网上应用店 - 闲鱼登录态导出](https://chromewebstore.google.com/detail/xianyu-login-state-extrac/eidlpfjiodpigmfcahkmlenhppfklcoa)  
   或加载仓库内 `chrome-extension/` 目录（开发者模式 → 加载已解压的扩展程序）
2. 在 Chrome 中登录 [https://www.goofish.com/](https://www.goofish.com/)
3. 点击扩展图标 → **Extract Login State**
4. 点击 **Copy to Clipboard** 复制完整 JSON
5. Web UI → **闲鱼账号管理** → 粘贴并保存

扩展输出的 JSON 可能包含以下字段（增强快照）：

| 字段 | 作用 |
|------|------|
| `cookies` | 登录 Cookie 列表 |
| `env` | 浏览器环境（UA、时区、屏幕等） |
| `headers` | 常见请求头 |
| `storage` | localStorage / sessionStorage 快照 |

爬虫检测到增强快照后，会自动应用这些参数，降低被风控识别的概率。

详细说明见：[chrome-extension/README.md](../chrome-extension/README.md)

---

## 登录态文件存放位置

| 路径 | 说明 |
|------|------|
| `state/*.json` | 多账号登录态（Web UI「闲鱼账号管理」导入） |
| `xianyu_state.json` | 根目录默认登录态（兼容旧版） |
| Docker 挂载 | `docker-compose.yaml` 中 `./state:/app/state` |

可通过环境变量 `ACCOUNT_STATE_DIR` 修改账号目录，默认为 `state`。

---

## 在任务中绑定账号

1. Web UI → **任务管理** → 创建或编辑任务
2. **账号策略** 选择：
   - `fixed`：固定使用某个账号（需选择 `account_state_file`）
   - `rotate`：从 `state/` 目录轮换
   - `auto`：有根目录 `xianyu_state.json` 时优先使用，否则使用账号池
3. 保存后启动任务

---

## 登录态失效的表现与处理

| 现象 | 可能原因 | 处理 |
|------|----------|------|
| 日志提示跳转登录页 / `LoginRequiredError` | Cookie 过期 | 重新导出并更新登录态 |
| 频繁出现验证码弹窗 | 请求过频或环境异常 | 降低任务频率；使用增强快照；必要时 `RUN_HEADLESS=false` |
| 任务连续失败被暂停 | `FailureGuard` 熔断保护 | 更新 Cookie 后自动恢复；或查看 `logs/task-failure-guard.json` |

**建议**：登录态建议 **每周检查一次**，失效后按本指南重新导入。

---

## 常见问题

### Q: 我复制了 Cookie 字符串，应该填到 `.env` 的 `COOKIES_STR` 吗？

A: 本项目当前 **没有** `COOKIES_STR` 环境变量。请通过 Web UI 或 `state/*.json` 文件管理登录态，不要写入 `.env`。

### Q: 只复制 Cookie 够吗？

A: 能用，但不如 Chrome 扩展导出的增强快照稳定。扩展会同时导出 UA、时区等，和 Cookie 一起加载更不容易触发风控。

### Q: Docker 里怎么更新登录态？

A: 在宿主机更新 `state/` 目录下的 JSON 文件（已挂载进容器），无需重建镜像。更新后重启任务即可。
