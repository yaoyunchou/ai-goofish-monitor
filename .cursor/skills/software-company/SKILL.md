---
name: software-company
description: >-
  Software development team SOP (PM, Architect, Engineer, QA). Use when the user
  wants full-team delivery, /software-company, 软件开发团队, 齐活林, or multi-agent
  feature development workflow.
icon: rocket
color: brand
---

# Software Company 软件开发团队

基于 `software-company/` 插件迁移的 Cursor 项目配置。

## ⚠️ 铁律：只改代码，不要运行服务

**团队所有成员（PM / 架构师 / 工程师 / QA）一律只修改代码，不得启动或运行任何服务。**

- **禁止**代跑 `start.sh` / `start.bat` / `dev_start.bat` / `python -m src.app` /
  `npm run dev` / `uvicorn ...` / `docker compose up` / `spider_v2.py` 等
  任何会占用端口或产生常驻进程的命令。
- 验证用**静态手段**：`pytest`、`npx vue-tsc -b --noEmit`、`npx vitest run`。
  **不要**用「先起服务再 curl」的方式验证。
- 确实启动了进程的，**必须在同一次任务内关闭**并确认端口释放。
- 交付完成即结束，**不要**主动把服务跑起来给用户测试——运行一律由用户手动执行。

## 本地端口约定

- 本项目本地开发端口为 **8010**（读 `.env` 的 `SERVER_PORT`）。
- 本机 **`8000` 被用户的另一个项目长期占用**，不要占用，也不要结束其进程。
- 前端 dev server 使用 **5173**。

## 成员（`.cursor/agents/`）

| 角色 | 调用方式 |
|------|----------|
| 交付总监 齐活林 | `/software-team-lead` 或自然语言「用软件开发团队」 |
| 产品经理 许清楚 | Task → `software-product-manager` |
| 架构师 高见远 | Task → `software-architect` |
| 工程师 寇豆码 | Task → `software-engineer` |
| QA 严过关 | Task → `software-qa-engineer` |

## 快速开始

1. 在 Agent 对话输入：`/software-team-lead 帮我做一个 xxx`
2. 或：`/software-company` 后描述需求
3. 主理人会判断快速模式 / BugFix / 标准 SOP，并用 Task 调度成员

## 工作流

- **快速模式**（默认）：工程师 → QA
- **BugFix**：工程师修复 → QA 回归
- **标准 SOP**：PM → 架构师 → 工程师 → QA

## 产物路径（建议）

- PRD 目录：`docs/prd/`（索引见 `docs/prd/README.md`；兼容入口 `docs/prd.md`）
- 技术方案：`docs/design/`（索引见 `docs/design/README.md`；全量架构 `architecture.md`；兼容入口 `docs/design.md`）
- 交付报告（可选）：`deliverables/software-company/<项目>-delivery-<日期>.md`

## 原始定义

完整 CodeBuddy 原文见 `software-company/agents/*.md`。
