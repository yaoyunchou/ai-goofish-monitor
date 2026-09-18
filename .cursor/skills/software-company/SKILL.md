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
