# nlm-setup 重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构 `nlm setup` 命令，引入 24h 缓存、明确的 local/global 绑定 flag、渐进式 next_step 提示，并更新 SKILL.md 编排脚本。

**Architecture:** 双文件存储（`.nlm/notebooks_cache.json` 存 API 缓存，`.nlm/config.json` 存绑定快照），`registry.py` 提供缓存读写与 schema 迁移，`nlm.py` 的 `cmd_setup` 全面重写，其他命令通过迁移助手兼容新 schema。

**Tech Stack:** Python 3.11+, pytest, `notebooklm` 库（notebook 对象字段：`id`, `title`, `sources_count`, `created_at`）

---

## API 实测说明

`notebooklm` 库的 notebook 对象**实际可用字段**（已在生产环境验证）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `nb.id` | str | UUID |
| `nb.title` | str | 笔记本标题 |
| `nb.sources_count` | int | 来源数量（注意：是 `sources_count` 不是 `source_count`） |
| `nb.created_at` | str | 创建时间（无修改时间字段） |

无 `description` 字段，缓存中存储空字符串占位，表格列改为 "Created" 而非 "Modified"。

---

## 文件变更清单

| 文件 | 变更类型 | 职责 |
|------|---------|------|
| `scripts/lib/client.py` | 扩展 | `list_notebooks()` 返回完整元数据 |
| `scripts/lib/registry.py` | 新增函数 | 缓存读写、schema 迁移助手、更新 `find_notebook_ids` |
| `scripts/nlm.py` | 重构 `cmd_setup` | 替换旧 flag，新增绑定逻辑和 next_step 输出；更新 `cmd_research`/`cmd_add` |
| `tests/test_registry.py` | 更新 + 新增 | 覆盖新 schema、缓存函数、迁移助手 |
| `tests/test_cli.py` | 更新 | 更新 `test_setup_list_notebooks` 匹配新输出格式 |
| `skills/nlm-setup/SKILL.md` | 完全重写 | 按规格文档第四节 |

---

## Task 1：扩展 `client.py` — `list_notebooks()` 返回完整元数据

**Files:**
- Modify: `scripts/lib/client.py:34-39`

- [ ] **Step 1: 确认现有 `list_notebooks()` 测试行为**

```bash
cd '/Users/marine/Code/NotebookLM SKILL/marine-notebooklm-skill'
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from lib import client
nbs = client.list_notebooks()
print('first notebook keys:', list(nbs[0].keys()) if nbs else 'empty')
"
```

预期输出：`first notebook keys: ['id', 'title']`（当前只有两个字段）

- [ ] **Step 2: 更新 `list_notebooks()` 增加元数据字段**

将 `scripts/lib/client.py` 第 34–39 行替换为：

```python
def list_notebooks() -> list[dict[str, Any]]:
    async def _run():
        async with await NotebookLMClient.from_storage() as client:
            nbs = await client.notebooks.list()
            return [
                {
                    "id":           nb.id,
                    "title":        nb.title,
                    "source_count": getattr(nb, "sources_count", 0),
                    "description":  "",
                    "created_at":   str(getattr(nb, "created_at", "")),
                }
                for nb in nbs
            ]
    return asyncio.run(_run())
```

- [ ] **Step 3: 验证新字段已返回**

```bash
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from lib import client
nbs = client.list_notebooks()
print('keys:', list(nbs[0].keys()) if nbs else 'empty')
print('first:', nbs[0] if nbs else 'none')
"
```

预期输出：`keys: ['id', 'title', 'source_count', 'description', 'created_at']`

- [ ] **Step 4: Commit**

```bash
git add scripts/lib/client.py
git commit -m "feat(client): extend list_notebooks with source_count and created_at"
```

---

## Task 2：`registry.py` — 新增缓存函数

**Files:**
- Modify: `scripts/lib/registry.py`
- Test: `tests/test_registry.py`

- [ ] **Step 1: 在 `registry.py` 顶部新增 datetime 导入**

将文件第 1–5 行替换为：

```python
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
```

- [ ] **Step 2: 在文件末尾追加两个缓存函数**

在 `find_notebook_ids` 之后追加：

```python
def load_notebooks_cache(project_path: Path) -> dict | None:
    """返回有效缓存内容，不存在或已过期返回 None。TTL 默认 24h。"""
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
    """将笔记本列表写入缓存，TTL 24h。"""
    nlm_dir = Path(project_path) / ".nlm"
    nlm_dir.mkdir(parents=True, exist_ok=True)
    (nlm_dir / "notebooks_cache.json").write_text(json.dumps({
        "cached_at": datetime.now().isoformat(timespec="seconds"),
        "ttl_hours": 24,
        "notebooks": notebooks,
    }, indent=2, ensure_ascii=False))
```

- [ ] **Step 3: 写失败测试 — 缓存不存在时返回 None**

在 `tests/test_registry.py` 末尾添加：

```python
from lib.registry import load_notebooks_cache, save_notebooks_cache


def test_load_notebooks_cache_missing(tmp_path):
    result = load_notebooks_cache(tmp_path)
    assert result is None


def test_save_and_load_notebooks_cache(tmp_path):
    notebooks = [{"id": "abc", "title": "Test", "source_count": 5, "description": "", "created_at": "2026-01-01"}]
    save_notebooks_cache(tmp_path, notebooks)
    result = load_notebooks_cache(tmp_path)
    assert result is not None
    assert result["ttl_hours"] == 24
    assert result["notebooks"] == notebooks
    assert (tmp_path / ".nlm" / "notebooks_cache.json").exists()
```

- [ ] **Step 4: 运行测试，确认失败**

```bash
cd '/Users/marine/Code/NotebookLM SKILL/marine-notebooklm-skill'
python3 -m pytest tests/test_registry.py::test_load_notebooks_cache_missing tests/test_registry.py::test_save_and_load_notebooks_cache -v
```

预期：`ImportError: cannot import name 'load_notebooks_cache'`（函数尚未存在）

- [ ] **Step 5: 运行测试，确认通过**

（函数已在 Step 2 添加）

```bash
python3 -m pytest tests/test_registry.py::test_load_notebooks_cache_missing tests/test_registry.py::test_save_and_load_notebooks_cache -v
```

预期：2 PASSED

- [ ] **Step 6: 写过期缓存测试**

在 `tests/test_registry.py` 继续追加：

```python
from unittest.mock import patch
from datetime import datetime, timedelta


def test_load_notebooks_cache_expired(tmp_path):
    notebooks = [{"id": "abc", "title": "Test", "source_count": 0, "description": "", "created_at": ""}]
    save_notebooks_cache(tmp_path, notebooks)
    # 伪造缓存写入时间为 25 小时前
    cache_file = tmp_path / ".nlm" / "notebooks_cache.json"
    import json as _json
    data = _json.loads(cache_file.read_text())
    stale_time = (datetime.now() - timedelta(hours=25)).isoformat(timespec="seconds")
    data["cached_at"] = stale_time
    cache_file.write_text(_json.dumps(data))

    result = load_notebooks_cache(tmp_path)
    assert result is None
```

- [ ] **Step 7: 运行测试确认通过**

```bash
python3 -m pytest tests/test_registry.py::test_load_notebooks_cache_expired -v
```

预期：PASSED

- [ ] **Step 8: Commit**

```bash
git add scripts/lib/registry.py tests/test_registry.py
git commit -m "feat(registry): add load/save_notebooks_cache with 24h TTL"
```

---

## Task 3：`registry.py` — schema 迁移助手 + 更新 `find_notebook_ids`

**Files:**
- Modify: `scripts/lib/registry.py`
- Test: `tests/test_registry.py`

- [ ] **Step 1: 在 `registry.py` 末尾（缓存函数之前）添加迁移助手**

在 `find_notebook_ids` 函数之前插入：

```python
def _resolve_local_id(config: dict) -> str | None:
    """支持新 schema (local_notebook.id) 和旧 schema (local_notebook_id) 两种格式。"""
    if local_nb := config.get("local_notebook"):
        return local_nb.get("id")
    return config.get("local_notebook_id")


def _resolve_global_ids(config: dict) -> list[str]:
    """支持新 schema (global_notebooks[].id) 和旧 schema (global_notebook_ids) 两种格式。"""
    if global_nbs := config.get("global_notebooks"):
        return [nb.get("id") for nb in global_nbs if nb.get("id")]
    return config.get("global_notebook_ids", [])
```

- [ ] **Step 2: 替换 `find_notebook_ids` 实现**

将现有 `find_notebook_ids` 函数替换为：

```python
def find_notebook_ids(scope: str, project_path: Path) -> list[str]:
    """Return ordered list of notebook IDs to try for given scope.

    Supports both new schema (local_notebook/global_notebooks objects)
    and old schema (local_notebook_id/global_notebook_ids strings) for migration.
    Global notebooks are now per-project (stored in .nlm/config.json).
    """
    ids: list[str] = []
    cfg = load_project_config(project_path)

    if scope in ("local", "auto"):
        if local_id := _resolve_local_id(cfg):
            ids.append(local_id)

    if scope in ("global", "auto"):
        ids.extend(_resolve_global_ids(cfg))

    return ids
```

- [ ] **Step 3: 写迁移助手的失败测试**

在 `tests/test_registry.py` 追加：

```python
from lib.registry import _resolve_local_id, _resolve_global_ids


def test_resolve_local_id_new_schema():
    config = {"local_notebook": {"id": "new-id", "title": "Test"}}
    assert _resolve_local_id(config) == "new-id"


def test_resolve_local_id_old_schema():
    config = {"local_notebook_id": "old-id"}
    assert _resolve_local_id(config) == "old-id"


def test_resolve_local_id_empty():
    assert _resolve_local_id({}) is None


def test_resolve_global_ids_new_schema():
    config = {"global_notebooks": [{"id": "g1"}, {"id": "g2"}]}
    assert _resolve_global_ids(config) == ["g1", "g2"]


def test_resolve_global_ids_old_schema():
    config = {"global_notebook_ids": ["g1", "g2"]}
    assert _resolve_global_ids(config) == ["g1", "g2"]


def test_resolve_global_ids_empty():
    assert _resolve_global_ids({}) == []
```

- [ ] **Step 4: 更新 `find_notebook_ids` 的测试（新 schema）**

将 `test_registry.py` 中原有的三个 `test_find_notebook_ids_*` 测试替换为：

```python
def test_find_notebook_ids_local_new_schema(tmp_path):
    save_project_config(tmp_path, {
        "local_notebook": {"id": "local-id", "title": "My NB"},
        "global_notebooks": [],
    })
    assert find_notebook_ids("local", tmp_path) == ["local-id"]


def test_find_notebook_ids_global_new_schema(tmp_path):
    save_project_config(tmp_path, {
        "local_notebook": None,
        "global_notebooks": [{"id": "g1"}, {"id": "g2"}],
    })
    assert find_notebook_ids("global", tmp_path) == ["g1", "g2"]


def test_find_notebook_ids_auto_returns_local_first_new_schema(tmp_path):
    save_project_config(tmp_path, {
        "local_notebook": {"id": "local-id", "title": "Local"},
        "global_notebooks": [{"id": "g1"}],
    })
    result = find_notebook_ids("auto", tmp_path)
    assert result[0] == "local-id"
    assert "g1" in result


def test_find_notebook_ids_old_schema_migration(tmp_path):
    """旧格式 config 仍能正常读取（向前兼容）。"""
    save_project_config(tmp_path, {
        "local_notebook_id": "old-local",
        "global_notebook_ids": ["old-g1"],
    })
    result = find_notebook_ids("auto", tmp_path)
    assert result == ["old-local", "old-g1"]
```

- [ ] **Step 5: 运行所有 registry 测试**

```bash
python3 -m pytest tests/test_registry.py -v
```

预期：全部 PASSED（旧的 `test_find_notebook_ids_global` 会失败，因为它测试的是已删除的 global_config 读取逻辑 — 已被上面的新测试替换）

- [ ] **Step 6: Commit**

```bash
git add scripts/lib/registry.py tests/test_registry.py
git commit -m "feat(registry): add schema migration helpers, update find_notebook_ids for per-project globals"
```

---

## Task 4：更新 `cmd_research` 和 `cmd_add` 读取新 schema

**Files:**
- Modify: `scripts/nlm.py:256-259, 303-308`

- [ ] **Step 1: 更新 `cmd_research` 读取 local notebook id**

将 `cmd_research` 中的：
```python
cfg = load_project_config(project_path)
notebook_id = cfg.get("local_notebook_id")
```
替换为：
```python
from lib.registry import _resolve_local_id
cfg = load_project_config(project_path)
notebook_id = _resolve_local_id(cfg)
```

（将 `from lib.registry import _resolve_local_id` 加到文件顶部的 import 块中）

- [ ] **Step 2: 更新 `cmd_add` 读取 local notebook id**

将 `cmd_add` 中的：
```python
notebook_id = cfg.get("local_notebook_id")
```
替换为：
```python
notebook_id = _resolve_local_id(cfg)
```

- [ ] **Step 3: 确认文件顶部 import 已更新**

`scripts/nlm.py` 顶部 import 块应包含：

```python
from lib.registry import (
    find_notebook_ids, load_global_config, load_project_config,
    save_global_config, save_project_config,
    load_notebooks_cache, save_notebooks_cache,
    _resolve_local_id,
)
```

- [ ] **Step 4: 运行现有集成测试（不需要真实 API，仅检查导入）**

```bash
python3 -c "
import sys; sys.path.insert(0, 'scripts')
import nlm
print('imports ok')
"
```

预期：`imports ok`

- [ ] **Step 5: Commit**

```bash
git add scripts/nlm.py
git commit -m "fix(nlm): update cmd_research and cmd_add to use new config schema"
```

---

## Task 5：重写 `cmd_setup` — 核心实现

**Files:**
- Modify: `scripts/nlm.py:48-122`

- [ ] **Step 1: 替换整个 `cmd_setup` 函数**

将 `scripts/nlm.py` 中 `cmd_setup` 函数（第 48–122 行）替换为以下完整实现：

```python
def _next_step_after_local() -> dict:
    return {
        "hint": "可选：从列表中选择一个或多个全局参考笔记本",
        "commands": [
            "nlm setup --add-global-notebook <UUID>",
            "nlm setup --add-global-notebook <UUID1> <UUID2>",
        ],
        "skip": "如不需要，setup 已完成，可直接使用 nlm ask",
    }


def _next_step_after_global() -> dict:
    return {
        "hint": "Setup 完成，可继续追加更多全局参考本或开始使用",
        "commands": [
            "nlm ask --question \"你的问题\"",
            "nlm setup --add-global-notebook <UUID>",
        ],
    }


def cmd_setup(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="nlm setup")
    parser.add_argument("--auth", action="store_true")
    parser.add_argument("--reauth", action="store_true")
    parser.add_argument("--notebook-list", action="store_true")
    parser.add_argument("--refresh", action="store_true",
                        help="Force refresh notebook list from API (bypass cache)")
    parser.add_argument("--add-local-notebook", metavar="UUID",
                        help="Bind a notebook as the project local notebook")
    parser.add_argument("--add-global-notebook", nargs="+", metavar="UUID",
                        help="Append one or more notebooks as global references")
    parser.add_argument("--create-local", metavar="TITLE",
                        help="Create a new notebook and bind it as local")
    parser.add_argument("--create-global", metavar="TITLE",
                        help="Create a new notebook and append it as global")
    parser.add_argument("--project-path", default=".", metavar="PATH")
    parsed = parser.parse_args(args)

    project_path = Path(parsed.project_path).expanduser().resolve()

    # ── Auth ──────────────────────────────────────────────────────────────────
    if parsed.reauth:
        clear_auth()
        _do_browser_auth(force=True)
        return

    if parsed.auth:
        _do_browser_auth()
        return

    # ── Status (bare call) ───────────────────────────────────────────────────
    if not any([parsed.notebook_list, parsed.add_local_notebook,
                parsed.add_global_notebook, parsed.create_local, parsed.create_global]):
        config = load_project_config(project_path)
        print(json.dumps({
            "status": "ok",
            "authenticated": is_authenticated(),
            "project_path": str(project_path),
            "local_notebook": config.get("local_notebook"),
            "global_notebooks": config.get("global_notebooks", []),
            "next_step": None,
        }, indent=2, ensure_ascii=False))
        return

    assert_authenticated()

    # ── Notebook list (with cache) ────────────────────────────────────────────
    if parsed.notebook_list:
        cache = None if parsed.refresh else load_notebooks_cache(project_path)
        cached = cache is not None

        if not cached:
            raw = client.list_notebooks()
            save_notebooks_cache(project_path, raw)
            cache = load_notebooks_cache(project_path)

        notebooks = cache["notebooks"]
        table = [
            {
                "#": i + 1,
                "UUID": nb["id"],
                "Title": nb["title"],
                "Sources": nb.get("source_count", 0),
                "Description": nb.get("description", ""),
                "Created": nb.get("created_at", "")[:16].replace("T", " "),
            }
            for i, nb in enumerate(notebooks)
        ]
        print(json.dumps({
            "action": "select_notebook",
            "cache": {
                "cached": cached,
                "cached_at": cache["cached_at"],
                "ttl_hours": cache["ttl_hours"],
            },
            "total": len(notebooks),
            "table": table,
            "next_step": {
                "hint": "选择一个作为本项目的 Local 笔记本，或新建一个",
                "commands": [
                    "nlm setup --add-local-notebook <UUID>",
                    'nlm setup --create-local "<新笔记本名称>"',
                ],
            },
        }, indent=2, ensure_ascii=False))
        return

    # ── Helpers: lookup notebook metadata from cache ──────────────────────────
    def _get_nb_meta(uuid: str) -> dict:
        """从缓存获取 notebook 元数据，缓存不存在时返回最小结构。"""
        cache = load_notebooks_cache(project_path)
        if cache:
            for nb in cache["notebooks"]:
                if nb["id"] == uuid:
                    return {
                        "id": nb["id"],
                        "title": nb.get("title", uuid[:12]),
                        "source_count": nb.get("source_count", 0),
                        "description": nb.get("description", ""),
                    }
        # UUID not in cache — return minimal stub
        return {"id": uuid, "title": uuid[:12], "source_count": 0, "description": ""}

    # ── Add local notebook ────────────────────────────────────────────────────
    if parsed.add_local_notebook:
        uuid = parsed.add_local_notebook
        meta = _get_nb_meta(uuid)
        config = load_project_config(project_path)
        config["local_notebook"] = meta
        if "global_notebooks" not in config:
            config["global_notebooks"] = []
        # Remove legacy keys if present
        config.pop("local_notebook_id", None)
        config.pop("global_notebook_ids", None)
        save_project_config(project_path, config)
        print(json.dumps({
            "status": "ok",
            "bound": "local",
            "local_notebook": meta,
            "next_step": _next_step_after_local(),
        }, indent=2, ensure_ascii=False))
        return

    # ── Add global notebooks ──────────────────────────────────────────────────
    if parsed.add_global_notebook:
        config = load_project_config(project_path)
        existing_global = config.get("global_notebooks", [])
        existing_ids = {nb["id"] for nb in existing_global}
        added = []
        for uuid in parsed.add_global_notebook:
            if uuid not in existing_ids:
                meta = _get_nb_meta(uuid)
                existing_global.append(meta)
                added.append(meta)
                existing_ids.add(uuid)
        config["global_notebooks"] = existing_global
        if "local_notebook" not in config:
            config["local_notebook"] = None
        config.pop("global_notebook_ids", None)
        save_project_config(project_path, config)
        print(json.dumps({
            "status": "ok",
            "bound": "global",
            "added": added,
            "global_notebooks_total": len(existing_global),
            "next_step": _next_step_after_global(),
        }, indent=2, ensure_ascii=False))
        return

    # ── Create local ──────────────────────────────────────────────────────────
    if parsed.create_local:
        nb = client.create_notebook(parsed.create_local)
        meta = {"id": nb["id"], "title": nb["title"], "source_count": 0, "description": ""}
        config = load_project_config(project_path)
        config["local_notebook"] = meta
        if "global_notebooks" not in config:
            config["global_notebooks"] = []
        config.pop("local_notebook_id", None)
        config.pop("global_notebook_ids", None)
        save_project_config(project_path, config)
        print(json.dumps({
            "status": "ok",
            "bound": "local",
            "created": True,
            "local_notebook": meta,
            "next_step": _next_step_after_local(),
        }, indent=2, ensure_ascii=False))
        return

    # ── Create global ─────────────────────────────────────────────────────────
    if parsed.create_global:
        nb = client.create_notebook(parsed.create_global)
        meta = {"id": nb["id"], "title": nb["title"], "source_count": 0, "description": ""}
        config = load_project_config(project_path)
        existing_global = config.get("global_notebooks", [])
        existing_global.append(meta)
        config["global_notebooks"] = existing_global
        if "local_notebook" not in config:
            config["local_notebook"] = None
        config.pop("global_notebook_ids", None)
        save_project_config(project_path, config)
        print(json.dumps({
            "status": "ok",
            "bound": "global",
            "created": True,
            "added": [meta],
            "global_notebooks_total": len(existing_global),
            "next_step": _next_step_after_global(),
        }, indent=2, ensure_ascii=False))
        return
```

- [ ] **Step 2: 确认旧 flag 已从文件中完全移除**

```bash
grep -n "notebook.id\|--create\b\|notebook_list.*action" scripts/nlm.py
```

预期：无匹配（旧的 `--notebook-id` 和 `--create` 已不存在）

- [ ] **Step 3: 确认新文件可正常导入**

```bash
python3 -c "import sys; sys.path.insert(0,'scripts'); import nlm; print('ok')"
```

预期：`ok`

- [ ] **Step 4: Commit**

```bash
git add scripts/nlm.py
git commit -m "feat(setup): rewrite cmd_setup with cache, add-local/global, create-local/global, next_step hints"
```

---

## Task 6：更新集成测试 `test_cli.py`

**Files:**
- Modify: `tests/test_cli.py`

- [ ] **Step 1: 更新 `test_setup_list_notebooks` 匹配新输出格式**

将 `test_setup_list_notebooks` 函数替换为：

```python
def test_setup_notebook_list():
    """--notebook-list 返回 table 格式、cache 信息和 next_step。"""
    out = run(["setup", "--notebook-list", "--project-path", PROJECT])
    assert out["action"] == "select_notebook"
    assert "cache" in out
    assert "cached_at" in out["cache"]
    assert isinstance(out["total"], int)
    assert out["total"] > 0
    assert isinstance(out["table"], list)
    first = out["table"][0]
    assert "#" in first
    assert "UUID" in first
    assert "Title" in first
    assert "Sources" in first
    assert "next_step" in out
    assert "hint" in out["next_step"]


def test_setup_notebook_list_refresh():
    """--refresh 强制从 API 拉取，cache.cached 为 False。"""
    out = run(["setup", "--notebook-list", "--refresh", "--project-path", PROJECT])
    assert out["action"] == "select_notebook"
    assert out["cache"]["cached"] is False


def test_setup_bare_returns_status():
    """裸 setup 返回当前绑定状态，不调用 API。"""
    out = run(["setup", "--project-path", PROJECT])
    assert out["status"] == "ok"
    assert "authenticated" in out
    assert "local_notebook" in out
    assert "global_notebooks" in out
    assert out["next_step"] is None
```

- [ ] **Step 2: 新增 `--add-local-notebook` 集成测试**

在 `test_cli.py` 末尾追加：

```python
def test_setup_add_local_notebook():
    """--add-local-notebook 绑定成功，输出 bound=local 和 next_step。"""
    # 先获取一个真实 UUID
    list_out = run(["setup", "--notebook-list", "--project-path", PROJECT])
    uuid = list_out["table"][0]["UUID"]

    out = run(["setup", "--add-local-notebook", uuid, "--project-path", PROJECT])
    assert out["status"] == "ok"
    assert out["bound"] == "local"
    assert out["local_notebook"]["id"] == uuid
    assert "next_step" in out
    assert "hint" in out["next_step"]


def test_setup_add_global_notebook():
    """--add-global-notebook 追加成功，输出 bound=global 和 total。"""
    list_out = run(["setup", "--notebook-list", "--project-path", PROJECT])
    # 取第二个（如有），避免与 local 重复
    uuid = list_out["table"][1]["UUID"] if len(list_out["table"]) > 1 else list_out["table"][0]["UUID"]

    out = run(["setup", "--add-global-notebook", uuid, "--project-path", PROJECT])
    assert out["status"] == "ok"
    assert out["bound"] == "global"
    assert isinstance(out["global_notebooks_total"], int)
    assert any(nb["id"] == uuid for nb in out["added"])
```

- [ ] **Step 3: 运行更新后的集成测试（需要真实 auth）**

```bash
cd '/Users/marine/Code/NotebookLM SKILL/marine-notebooklm-skill'
python3 tests/test_cli.py 2>&1 | tail -20
```

预期：所有 setup 相关测试 ✅

- [ ] **Step 4: Commit**

```bash
git add tests/test_cli.py
git commit -m "test(cli): update test_setup_* for new flag names and output schema"
```

---

## Task 7：重写 `skills/nlm-setup/SKILL.md`

**Files:**
- Modify: `skills/nlm-setup/SKILL.md`

- [ ] **Step 1: 完全替换文件内容**

将 `skills/nlm-setup/SKILL.md` 替换为以下内容：

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

- [ ] **Step 2: 同步到 `~/.claude/skills/nlm-setup/SKILL.md`**

```bash
cp '/Users/marine/Code/NotebookLM SKILL/marine-notebooklm-skill/skills/nlm-setup/SKILL.md' \
   "$HOME/.claude/skills/nlm-setup/SKILL.md"
```

- [ ] **Step 3: Commit 并推送**

```bash
git add skills/nlm-setup/SKILL.md
git commit -m "docs(skill): rewrite nlm-setup SKILL.md with 3-step orchestration flow"
git push origin main
```

---

## 最终验证

- [ ] **运行全部单元测试**

```bash
cd '/Users/marine/Code/NotebookLM SKILL/marine-notebooklm-skill'
python3 -m pytest tests/test_registry.py -v
```

预期：全部 PASSED

- [ ] **运行集成测试**

```bash
python3 tests/test_cli.py 2>&1 | tail -15
```

预期：Passed: N/N, Failed: 0/N

- [ ] **手动验证 setup 流程**

```bash
INVOKE="bash $HOME/.claude/skills/nlm/scripts/invoke.sh"
$INVOKE setup --notebook-list | python3 -m json.tool | head -30
```

预期：输出包含 `action: select_notebook`、`table` 数组、`next_step.hint`
