# 项目文档

本目录包含闲鱼智能监控系统的详细使用与配置说明。

## 文档索引

### 📖 项目与架构（开发者向）

| 文档 | 说明 |
|------|------|
| [项目说明文档](./project-overview.md) | 项目全貌：定位、技术栈、目录结构、核心概念、数据流、发展历程 |
| [架构文档](./architecture.md) | 分层架构、模块职责、运行时进程模型、核心执行链路、数据模型、配置体系、设计决策 |
| [功能文档](./features.md) | 前后端全部功能点、API 端点清单、任务配置、通知渠道、命令行、配置项、测试体系 |

### 🔍 页面探索（爬虫/集成向）

| 文档 | 说明 |
|------|------|
| [用户主页探索](./exploration/personal-profile-exploration.md) | C 端 `www.goofish.com/personal` 页面结构、MTOP API、采集流程 |
| [卖家工作台探索](./exploration/seller-workbench-exploration.md) | `seller.goofish.com` 数据总览、datacompass API、经营指标 |

### 🧑‍💻 使用与配置（使用者向）

| 文档 | 说明 |
|------|------|
| [用户使用指南](./user-guide.md) | 从安装、配置到日常使用的完整流程 |
| [闲鱼 Cookie 获取指南](./getting-xianyu-cookies.md) | 手动抓包与 Chrome 扩展两种登录态导入方式 |
| [AI 提供方配置：OpenAI 与 Cursor SDK](./ai-provider.md) | OpenAI 兼容接口与 Cursor SDK 的配置、切换与原理说明 |
| [Supabase（PostgreSQL）接入指南](./database-supabase-integration.md) | 数据库连接、建表、自检与迁移 |

### 🗄️ 归档参考

| 文档 | 说明 |
|------|------|
| [数据库 MySQL 迁移计划](./database-mysql-migration-plan.md) | 历史迁移方案（已由 PostgreSQL 方案取代，归档参考） |

## 阅读建议

- **第一次使用项目** → 先看 [用户使用指南](./user-guide.md)，再补 [项目说明文档](./project-overview.md)
- **了解系统怎么设计** → [架构文档](./architecture.md)
- **查某个功能/接口/配置怎么用** → [功能文档](./features.md)
- **爬虫提示登录失效** → [闲鱼 Cookie 获取指南](./getting-xianyu-cookies.md)
- **想改用 Cursor 模型** → [AI 提供方配置](./ai-provider.md)

## 相关资源

- 项目根目录 [README.md](../README.md)
- Chrome 扩展说明：[chrome-extension/README.md](../chrome-extension/README.md)
- 环境变量模板：[.env.example](../.env.example)
