# 项目文档

本目录包含闲鱼智能监控系统的详细使用与配置说明。

## 文档索引

### 📋 产品需求（PRD）

| 文档 | 说明 |
|------|------|
| [PRD 目录](./prd/README.md) | 全部产品需求文档索引 |
| [卖家订阅 · 风控与运营](./prd/seller-subscription-anti-risk.md) | 大规模采集降速、多账号分工、无头调度（2026-09-17） |
| [项目健康度分析](./prd/project-health.md) | 文档/测试缺口审计与 5 阶段整改计划 |

### 🏗️ 技术方案（Design）

| 文档 | 说明 |
|------|------|
| [设计文档目录](./design/README.md) | 架构、数据库、采集链路等技术方案索引 |
| [系统架构](./design/architecture.md) | 分层架构、进程模型、数据模型、设计决策 |
| [卖家订阅采集方案](./design/seller-subscription-scrape.md) | 风控节奏、无头调度、实现索引（对应上列 PRD） |
| [PostgreSQL 接入](./design/database-supabase-integration.md) | 数据库连接、建表与迁移 |

### 📖 项目与架构（开发者向）

| 文档 | 说明 |
|------|------|
| [项目说明文档](./project-overview.md) | 项目全貌：定位、技术栈、目录结构、核心概念、数据流、发展历程 |
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
| [Supabase（PostgreSQL）接入指南](./design/database-supabase-integration.md) | 数据库连接、建表、自检与迁移 |

### 🗄️ 归档参考

| 文档 | 说明 |
|------|------|
| [数据库 MySQL 迁移计划](./design/database-mysql-migration-plan.md) | 历史迁移方案（已由 PostgreSQL 方案取代，归档参考） |

## 阅读建议

- **第一次使用项目** → 先看 [用户使用指南](./user-guide.md)，再补 [项目说明文档](./project-overview.md)
- **了解系统怎么设计** → [技术方案目录](./design/README.md) / [架构文档](./design/architecture.md)
- **查某个功能/接口/配置怎么用** → [功能文档](./features.md)
- **爬虫提示登录失效** → [闲鱼 Cookie 获取指南](./getting-xianyu-cookies.md)
- **想改用 Cursor 模型** → [AI 提供方配置](./ai-provider.md)

## 相关资源

- 项目根目录 [README.md](../README.md)
- Chrome 扩展说明：[chrome-extension/README.md](../chrome-extension/README.md)
- 环境变量模板：[.env.example](../.env.example)
