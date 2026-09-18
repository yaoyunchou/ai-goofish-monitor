# Web UI — 闲鱼智能监控前端

Vue 3 + Vite + TypeScript + Tailwind CSS + shadcn-vue（reka-ui）。

## 技术栈

| 类别 | 选型 |
|------|------|
| 框架 | Vue 3（Composition API + `<script setup>`） |
| 构建 | Vite 7 |
| 路由 | Vue Router 4 |
| 样式 | Tailwind CSS 3 + `tailwindcss-animate` |
| 组件 | shadcn-vue（reka-ui 无头组件） |
| 图标 | lucide-vue-next |
| i18n | vue-i18n（zh-CN / en-US） |
| 测试 | Vitest + jsdom |

## 目录结构

```
web-ui/
├── src/
│   ├── api/              # REST 客户端（tasks、results、seller-subscriptions 等）
│   ├── components/       # UI 组件（layout、tasks、results、ui/*）
│   ├── composables/      # useAuth、useTasks、useWebSocket 等
│   ├── i18n/             # 国际化消息与工具函数
│   ├── layouts/          # MainLayout
│   ├── lib/              # 工具（cn、goofish 链接拼接）
│   ├── router/           # 路由定义（13+ 页面）
│   ├── services/         # WebSocket
│   ├── types/            # TypeScript 类型
│   └── views/            # 页面级组件
├── vite.config.ts        # 构建输出 ../dist，开发代理 /api /auth /ws
└── vitest.setup.ts       # 测试环境 localStorage 初始化
```

## 开发

```bash
# 安装依赖
npm install

# 启动开发服务器（默认 http://localhost:5173）
# 需同时启动后端：python -m src.app
npm run dev

# 类型检查 + 生产构建（产物写入仓库根目录 dist/）
npm run build

# 预览构建结果
npm run preview
```

开发模式下 Vite 将 `/api`、`/auth` 代理到 `http://127.0.0.1:8000`，`/ws` 代理到后端 WebSocket。后端未启动时 API 请求返回 502 JSON 提示。

## 测试

```bash
npm test          # Vitest 一次性运行（CI 使用）
npm run test:watch  # 监听模式
```

当前 smoke 覆盖：

| 文件 | 内容 |
|------|------|
| `src/lib/utils.test.ts` | `cn()` Tailwind 类合并 |
| `src/lib/goofish.test.ts` | 闲鱼商品链接拼接 |
| `src/router/routes.smoke.test.ts` | 核心路由与 meta.titleKey |
| `src/i18n/smoke.test.ts` | 中英 route 文案、相对时间格式化 |

## 主要路由

| 路径 | 页面 |
|------|------|
| `/dashboard` | 监控概览 |
| `/tasks` | 任务管理 |
| `/accounts` | 闲鱼账号管理 |
| `/results` | 结果查看 |
| `/seller-subscriptions/sellers` | 卖家订阅 — 卖家列表 |
| `/seller-subscriptions/items` | 卖家订阅 — 商品列表 |
| `/seller-subscriptions/items/:itemId` | 商品详情 |
| `/seller-subscriptions/collection` | 采集控制台 |
| `/shop-analytics` | 店铺分析（订阅日指标看板） |
| `/logs` | 运行日志 |
| `/settings` | 系统设置 |

完整路由见 `src/router/index.ts`。

## 与后端集成

- 认证：`POST /auth/status`，登录态存 `localStorage`
- 实时日志：WebSocket `/ws`（`services/websocket.ts`）
- 构建产物由 FastAPI 静态托管（`dist/`），Docker 多阶段构建见根目录 `Dockerfile`

## 相关文档

- [用户使用指南](../docs/user-guide.md)
- [功能说明](../docs/features.md)
- [架构说明](../docs/design/architecture.md)
- 变更记录：[log.md](./log.md)
