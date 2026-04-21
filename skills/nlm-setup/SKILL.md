---
name: nlm-setup
description: >
  初始化项目的 NotebookLM 配置：绑定本地笔记本和全局参考笔记本。
  当用户说"初始化 NotebookLM"、"配置笔记本"、"绑定 notebook"、
  "setup nlm"、"这个项目用哪个笔记本"时触发。
  Do NOT use for: querying notebooks (use nlm-ask), authentication (use nlm setup --auth).
allowed-tools:
  - Bash
---

# nlm-setup — 项目笔记本配置

```bash
INVOKE="bash $HOME/.claude/skills/nlm/scripts/invoke.sh"
```

## 命令速查

| 命令 | 作用 |
|------|------|
| `$INVOKE setup` | 查看当前配置（零 API） |
| `$INVOKE setup --auth` | 首次 Google 认证 |
| `$INVOKE setup --reauth` | 重新认证 |
| `$INVOKE setup --notebook-list` | 列出账号下所有笔记本（24h 缓存） |
| `$INVOKE setup --notebook-list --refresh` | 强制从 API 重新拉取列表 |
| `$INVOKE setup --add-local-notebook <UUID>` | 绑定为项目本地笔记本（唯一） |
| `$INVOKE setup --add-global-notebook <UUID> [UUID2...]` | 追加全局参考笔记本（可多个） |
| `$INVOKE setup --create-local <title>` | 新建笔记本并绑定为 local |
| `$INVOKE setup --create-global <title>` | 新建笔记本并追加为 global |

## 标准初始化流程（三步）

### Step 1 — 展示笔记本列表

```bash
$INVOKE setup --notebook-list
```

将输出中的 `table` 以 Markdown 格式展示给用户，**必须包含所有列：`#`、`UUID`、`Title`、`Sources`、`Created`**。示例格式：

| # | UUID | Title | Sources | Created |
|---|------|-------|---------|---------|
| 1 | 8b3c7934-... | Claude Code实战 | 0 | 2026-04-19 |

读取 `next_step.hint` 后询问：
> "请选择一个作为本项目的**本地笔记本**（输入序号 # 或 UUID），或告诉我新建一个。"

### Step 2 — 绑定本地笔记本

用户选择已有笔记本（接受 #序号、UUID、名称任一形式）：
- 从 table 查到对应 UUID
- 执行 `$INVOKE setup --add-local-notebook <UUID>`

用户希望新建：
- 询问："请告诉我新笔记本的名称"
- 执行 `$INVOKE setup --create-local "<title>"`

绑定成功后，读取 `next_step.hint`，询问：
> "是否需要添加**全局参考笔记本**？可选择一个或多个（输入序号或 UUID，空格分隔）。"

### Step 3 — 绑定全局参考笔记本（可选）

用户选择添加：
- 从 table 查到对应 UUID 列表
- 执行 `$INVOKE setup --add-global-notebook <UUID1> <UUID2> ...`

用户跳过：
- 告知："Setup 完成，可以使用 `nlm ask` 开始提问了。"

可随时追加：用户可再次运行 `--add-global-notebook` 添加更多全局参考本。

## 查看当前状态

```bash
$INVOKE setup
```

直接读本地 config，不调用 API，即时展示当前绑定情况。

## 缓存说明

- 笔记本列表缓存 24 小时于 `.nlm/notebooks_cache.json`
- 若缓存过期，`--notebook-list` 自动刷新
- 需立即获取最新数据：`--notebook-list --refresh`

## 错误处理

| 错误 | 处理方式 |
|------|---------|
| `"authenticated: false"` | 告知用户先运行 `$INVOKE setup --auth` |
| `"error": "cache_missing"` | 提示先运行 `--notebook-list` 生成缓存 |
| `"error": "uuid_not_found"` | UUID 不在缓存中，建议 `--refresh` 后重试 |
| `"error": "local_already_bound"` | 已有本地笔记本，询问用户是否确认覆盖 |
