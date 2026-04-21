# nlm-setup 重设计规格文档

**日期**：2026-04-21  
**项目**：marine-notebooklm-skill  
**范围**：`nlm setup` 命令重构 — 笔记本列表缓存、全局/本地笔记本绑定逻辑、SKILL.md 编排重写

---

## 背景与目标

现有 `nlm setup` 存在三个核心问题：

1. `--notebook-list` 每次直接调用 API，无缓存，慢且浪费
2. 无法通过命令区分"绑定为本地"还是"绑定为全局"，语义模糊
3. `SKILL.md` 未描述完整的多步初始化流程，Claude 缺乏编排依据

目标：重构命令接口、引入双层 JSON 存储、实现渐进式提示，使初始化流程清晰且可被 Claude 完整编排。

---

## 设计决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| 全局笔记本存储位置 | 每项目 `.nlm/config.json` | 解耦，不同项目可维护不同全局参考本 |
| 笔记本列表元数据 | 完整版（含 source_count、description） | 字段保存在 config 快照中，绑定后免 API |
| 缓存位置 | 项目级 `.nlm/notebooks_cache.json` | 与项目上下文绑定，不跨项目污染 |
| `--notebook-id` / `--create` | 完全移除，无别名 | 消除歧义，统一使用新命名 |

---

## 第一节：数据架构

### `.nlm/notebooks_cache.json`（API 调用结果缓存）

```json
{
  "cached_at": "2026-04-21T10:00:00",
  "ttl_hours": 24,
  "notebooks": [
    {
      "id": "abc-uuid",
      "title": "船舶流体力学讲义",
      "source_count": 52,
      "description": "",
      "last_modified": "2026-04-20T16:17:18"
    },
    {
      "id": "xyz-uuid",
      "title": "SINAN 规范文档",
      "source_count": 89,
      "description": "CCS/COLREGS 合规参考",
      "last_modified": "2026-04-19T09:30:00"
    }
  ]
}
```

- 只缓存 API 原始列表，不含绑定关系
- `--refresh` 强制覆盖，TTL 过期自动刷新
- 由 `--notebook-list` 写入；绑定操作只读不写

### `.nlm/config.json`（绑定关系 + 元数据快照）

```json
{
  "local_notebook": {
    "id": "abc-uuid",
    "title": "船舶流体力学讲义",
    "source_count": 52,
    "description": ""
  },
  "global_notebooks": [
    {
      "id": "xyz-uuid",
      "title": "SINAN 规范文档",
      "source_count": 89,
      "description": "CCS/COLREGS 合规参考"
    }
  ]
}
```

- 绑定时从缓存复制元数据快照，不触发额外 API 调用
- `nlm setup`（裸调用）直接读此文件，零 API 开销
- `source_count` / `description` 为绑定时刻快照，不实时更新

---

## 第二节：CLI 接口

### 完整命令清单

| 命令 | 说明 |
|------|------|
| `nlm setup` | 查看当前配置（零 API） |
| `nlm setup --auth` | 首次 Google 认证 |
| `nlm setup --reauth` | 重新认证（清除现有 session） |
| `nlm setup --notebook-list` | 列出账号下所有笔记本（24h 缓存） |
| `nlm setup --notebook-list --refresh` | 强制从 API 重新拉取列表 |
| `nlm setup --add-local-notebook <UUID>` | 绑定为项目本地笔记本（唯一，覆盖已有） |
| `nlm setup --add-global-notebook <UUID> [UUID2...]` | 追加全局参考笔记本（支持多个） |
| `nlm setup --create-local <title>` | 新建笔记本并绑定为 local |
| `nlm setup --create-global <title>` | 新建笔记本并追加为 global |

**移除**：`--notebook-id`、`--create`（无别名，无向后兼容）

### 渐进提示输出格式

每个命令的 JSON 响应末尾统一包含 `next_step` 字段，供 Claude 读取并转述。

**`--notebook-list` 输出**
```json
{
  "action": "select_notebook",
  "cache": { "cached": true, "cached_at": "2026-04-21T09:00:00", "ttl_hours": 24 },
  "total": 36,
  "table": [
    { "#": 1, "UUID": "abc-uuid", "Title": "船舶流体力学讲义", "Sources": 52, "Description": "", "Modified": "2026-04-20 16:17" },
    { "#": 2, "UUID": "xyz-uuid", "Title": "SINAN 规范文档",   "Sources": 89, "Description": "CCS/COLREGS",   "Modified": "2026-04-19 09:30" }
  ],
  "next_step": {
    "hint": "选择一个作为本项目的 Local 笔记本，或新建一个",
    "commands": [
      "nlm setup --add-local-notebook <UUID>",
      "nlm setup --create-local \"<新笔记本名称>\""
    ]
  }
}
```

**`--add-local-notebook` 输出**
```json
{
  "status": "ok",
  "bound": "local",
  "local_notebook": { "id": "abc-uuid", "title": "船舶流体力学讲义", "source_count": 52 },
  "next_step": {
    "hint": "可选：从列表中选择一个或多个全局参考笔记本",
    "commands": [
      "nlm setup --add-global-notebook <UUID>",
      "nlm setup --add-global-notebook <UUID1> <UUID2>"
    ],
    "skip": "如不需要，setup 已完成，可直接使用 nlm ask"
  }
}
```

**`--add-global-notebook` 输出**
```json
{
  "status": "ok",
  "bound": "global",
  "added": [
    { "id": "xyz-uuid", "title": "SINAN 规范文档", "source_count": 89 }
  ],
  "global_notebooks_total": 1,
  "next_step": {
    "hint": "Setup 完成，可继续追加更多全局参考本或开始使用",
    "commands": [
      "nlm ask --question \"你的问题\"",
      "nlm setup --add-global-notebook <UUID>"
    ]
  }
}
```

**`--create-local` / `--create-global` 输出**

新建后输出格式与 `--add-local-notebook` / `--add-global-notebook` 完全相同，额外包含 `"created": true` 字段用于区分：
```json
{
  "status": "ok",
  "bound": "local",
  "created": true,
  "local_notebook": { "id": "new-uuid", "title": "My New Notebook", "source_count": 0 },
  "next_step": { ... }
}
```

**裸调用 `nlm setup`**
```json
{
  "status": "ok",
  "authenticated": true,
  "project_path": "/Users/marine/Code/avds",
  "local_notebook": { "id": "abc-uuid", "title": "船舶流体力学讲义", "source_count": 52 },
  "global_notebooks": [
    { "id": "xyz-uuid", "title": "SINAN 规范文档", "source_count": 89 }
  ],
  "next_step": null
}
```

---

## 第三节：缓存机制与 `client.py` 扩展

### 缓存读写流程

```
nlm setup --notebook-list
    ↓
读 .nlm/notebooks_cache.json
    ├── 不存在 / cached_at 超过 24h  → 调用 API → 写入缓存 → 返回
    └── 有效期内                     → 直接读缓存返回

nlm setup --notebook-list --refresh
    ↓
跳过缓存判断 → 调用 API → 覆盖写入缓存 → 返回
```

绑定操作（`--add-local-notebook`、`--add-global-notebook`、`--create-local`、`--create-global`）只读缓存取元数据，不写缓存。若缓存不存在则返回 `"error": "cache_missing"`。

### 缓存失效三种触发

| 触发 | 处理 |
|------|------|
| 首次运行（文件不存在） | 自动拉取 API，写入缓存 |
| TTL 过期（超 24h） | 自动拉取 API，覆盖缓存 |
| 用户主动 `--refresh` | 强制拉取 API，覆盖缓存 |

### `registry.py` 新增函数

```python
def load_notebooks_cache(project_path: Path) -> dict | None:
    """返回缓存内容，不存在或已过期返回 None。"""
    cache_file = Path(project_path) / ".nlm" / "notebooks_cache.json"
    if not cache_file.exists():
        return None
    data = json.loads(cache_file.read_text())
    cached_at = datetime.fromisoformat(data["cached_at"])
    ttl = timedelta(hours=data.get("ttl_hours", 24))
    if datetime.now() - cached_at > ttl:
        return None
    return data


def save_notebooks_cache(project_path: Path, notebooks: list[dict]) -> None:
    nlm_dir = Path(project_path) / ".nlm"
    nlm_dir.mkdir(parents=True, exist_ok=True)
    (nlm_dir / "notebooks_cache.json").write_text(json.dumps({
        "cached_at": datetime.now().isoformat(timespec="seconds"),
        "ttl_hours": 24,
        "notebooks": notebooks,
    }, indent=2, ensure_ascii=False))
```

### `client.py` — `list_notebooks()` 扩展

```python
def list_notebooks() -> list[dict[str, Any]]:
    async def _run():
        async with await NotebookLMClient.from_storage() as client:
            nbs = await client.notebooks.list()
            return [
                {
                    "id":            nb.id,
                    "title":         nb.title,
                    "source_count":  getattr(nb, "source_count", 0),
                    "description":   getattr(nb, "description", ""),
                    "last_modified": getattr(nb, "updated_at", ""),
                }
                for nb in nbs
            ]
    return asyncio.run(_run())
```

> `source_count`、`description`、`updated_at` 使用 `getattr(..., default)` 防御性取值。实现前需实测 `notebooklm` 库实际返回哪些字段，缺失字段降级为空值而非崩溃。

---

## 第四节：`nlm-setup` SKILL.md

```markdown
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

将输出中的 `table` 以 Markdown 格式展示给用户，读取 `next_step.hint` 后询问：
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
```

---

## 实现影响范围

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `scripts/nlm.py` | 重构 `cmd_setup` | 替换所有旧 flag，增加新 flag 和渐进提示输出 |
| `scripts/lib/registry.py` | 新增函数 | `load_notebooks_cache`、`save_notebooks_cache`、更新 config schema |
| `scripts/lib/client.py` | 扩展 | `list_notebooks()` 增加 source_count / description / last_modified |
| `skills/nlm-setup/SKILL.md` | 完全重写 | 按本文第四节内容 |
| `.nlm/config.json` schema | 破坏性变更 | `local_notebook_id`(string) → `local_notebook`(object)；`global_notebook_ids`(list[str]) → `global_notebooks`(list[object]) |

> **迁移注意**：`config.json` schema 变更为破坏性变更。`cmd_setup` 实现中需检测旧格式（`local_notebook_id` 字段存在）并自动迁移为新格式，或在文档中说明需重新运行 `--add-local-notebook`。
