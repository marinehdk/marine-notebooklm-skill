# nlm Source Management — Design Spec

**Date:** 2026-04-24  
**Status:** Approved

## Problem

`/nlm-research --add-sources` 会在每次调研时重复导入相同 URL，导致笔记本来源堆积。  
`/nlm-add` 也没有重复检查。目前没有手动删除或去重来源的指令。

## Scope

3 处改动，全部叠加在现有文件上，不新建模块：

| 改动 | 文件 | 性质 |
|------|------|------|
| `nlm-add` URL 重复检查 | `scripts/nlm.py` + `scripts/lib/client.py` | 修改 |
| `nlm delete` 子命令 + skill | `scripts/nlm.py` + `skills/nlm-delete/SKILL.md` | 新增 |
| `nlm deduplicate` 子命令 + skill | `scripts/nlm.py` + `skills/nlm-deduplicate/SKILL.md` | 新增 |

`client.py` 中 `deduplicate_notebook_sources()` 已就绪（由 research 去重工作引入）。

## Interface

### 1. `nlm-add` — URL 重复检查（静默跳过）

```bash
nlm add --url "https://..." --project-path "."
nlm add --note "内容" --title "标题" --project-path "."
```

**行为变更：** 仅对 `--url` 模式生效。在调用 `client.sources.add_url()` 前，先 `list()` 现有来源，若 URL 已存在（忽略大小写 + 去尾斜杠）则静默跳过。

**新输出（重复时）：**
```json
{"status": "skipped", "reason": "already_exists", "source": {"id": "...", "title": "..."}}
```

**原有输出（成功添加）：**
```json
{"status": "ok", "type": "url", "source": {"id": "...", "title": "..."}}
```

`--note` 模式不做重复检查（文本内容无稳定唯一键）。

---

### 2. `nlm delete` — 按 URL 或 ID 删除来源

```bash
nlm delete --url "https://..."          # 按 URL 匹配删除（忽略大小写 + 尾斜杠）
nlm delete --source-id "abc123"         # 按 ID 精确删除
nlm delete --project-path "."          # 默认当前目录
```

需提供 `--url` 或 `--source-id` 其中之一，否则报错。

**输出：**
```json
// 成功
{"status": "ok", "deleted": {"id": "...", "title": "..."}}

// 未找到
{"status": "not_found", "url": "https://..."}

// 未配置笔记本
{"error": "No local notebook configured. Run: nlm setup"}
```

**`client.py` 新增函数：**
```python
def delete_source(notebook_id: str, source_id: str) -> bool:
    """Delete a source by ID. Returns True if deleted."""
```

**Skill 触发规则：** 用户触发（不自动触发）。用户需提供 `--url` 或 `--source-id`，否则要求补充。

---

### 3. `nlm deduplicate` — 手动去重笔记本来源

```bash
nlm deduplicate --project-path "."
```

复用 `deduplicate_notebook_sources()`，按 URL 分组，保留最早添加的，删除其余重复项。

**输出：**
```json
{"status": "ok", "removed": 3, "kept": 12}
// removed: 0 时 Claude 提示"笔记本来源无重复"
```

**Skill 触发规则：** 用户触发（不自动触发）。用于手动清理，区别于 `nlm-research` 中的自动去重。

## Architecture

```
scripts/
  nlm.py              ← 新增 cmd_delete(), cmd_deduplicate(); 修改 cmd_add()
  lib/
    client.py         ← 新增 delete_source(); 修改 add_url() 加重复检查
skills/
  nlm-delete/
    SKILL.md          ← 新建
  nlm-deduplicate/
    SKILL.md          ← 新建
  nlm-add/
    SKILL.md          ← 更新（说明 skipped 响应）
```

## Trigger Rules Summary

| Skill | 自动触发 | 用户触发 |
|-------|---------|---------|
| `nlm-add` | ❌ | ✅ |
| `nlm-delete` | ❌ | ✅ |
| `nlm-deduplicate` | ❌ | ✅ |
| `nlm-research`（内含去重） | ✅ | ✅ |

## Out of Scope

- `/nlm-list`（列出所有来源） — 不在本次范围，`delete --url` 不强依赖它
- `--note` 重复检查 — 文本无稳定唯一键，跳过
- 全局笔记本的 delete / deduplicate — 全局笔记本只读，不支持写操作
