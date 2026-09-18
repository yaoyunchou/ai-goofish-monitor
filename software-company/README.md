# Software Company（CodeBuddy → Cursor）

本目录为 CodeBuddy 插件原始定义；**Cursor 可用配置**已迁移到：

- `.cursor/agents/software-*.md` — 5 个子代理
- `.cursor/skills/software-company/SKILL.md` — 团队入口 Skill

## 在 Cursor 中测试

```
/software-team-lead 帮我给 web-ui 加一个 xxx 功能
```

或：

```
/software-company
做一个简单的 Todo 页面，走快速模式
```

## 成员

| ID | 角色 |
|----|------|
| software-team-lead | 齐活林 · 交付总监 |
| software-product-manager | 许清楚 · 产品经理 |
| software-architect | 高见远 · 架构师 |
| software-engineer | 寇豆码 · 工程师 |
| software-qa-engineer | 严过关 · QA |

## 与 CodeBuddy 的差异

- `TeamCreate` / `SendMessage` → Cursor **Task** 子代理
- 成员产出通过 Task 返回值回传主理人
- 已按本项目技术栈（FastAPI + Vue 3）补充工程师/QA 约定
