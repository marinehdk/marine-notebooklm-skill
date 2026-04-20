---
name: nlm
description: >
  NotebookLM 万能入口调度器。接受任何自然语言，自动路由到 nlm-ask、nlm-research、nlm-plan、
  nlm-auth、nlm-setup。当用户说"查一下 NotebookLM"、"问问我的笔记本"、"notebook 里怎么说的"、
  "用 NotebookLM 研究一下"、"比较方案"、"NLM 登录"等场景时触发。
  Do NOT use for: general web search (use firecrawl), local file search (use grep/find), code generation.
allowed-tools:
  - Bash
---

# nlm — NotebookLM 调度器

```
INVOKE="bash $HOME/.claude/skills/notebooklm-superpower/scripts/invoke.sh"
```

## 路由规则

分析用户输入，路由到最匹配的子 skill：

| 意图信号 | 路由到 | 触发关键词 |
|---------|--------|-----------|
| 问一个具体事实/查阅文档 | **nlm-ask** | "是什么"、"怎么"、"查一下"、"问问"、"notebook里" |
| 深入研究/调研某议题 | **nlm-research** | "研究"、"调研"、"深入了解"、"查找资料"、"research" |
| 比较方案/做决策 | **nlm-plan** | "哪个更好"、"比较"、"选择"、"评估方案"、"compare" |
| 登录/认证 | **nlm-auth** | "登录"、"认证"、"auth"、"reauth"、"过期" |
| 初始化/配置笔记本 | **nlm-setup** | "初始化"、"配置"、"添加笔记本"、"setup"、"绑定" |

## 快速状态检查

```bash
$INVOKE status
```

输出当前 auth 状态、已配置项目数和 session 上下文。

## 调度逻辑

1. 读取用户输入，识别主要意图
2. 如果意图明确 → 直接按上表路由，执行对应 skill 的操作
3. 如果意图模糊（如"帮我查一下"，没有具体方向）→ 先执行 `$INVOKE status`，再问用户具体问题是什么
4. 永远不要猜测 notebook ID，先查 status 再操作

## 通用前置检查

每次使用前先确认 auth 有效：

```bash
$INVOKE auth status
```

如果返回 `❌` → 提示用户运行 nlm-auth。
