# nlm Source Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add URL dedup to `nlm-add`, plus new `nlm delete` and `nlm deduplicate` commands, each with a corresponding skill file.

**Architecture:** All changes are additive — new functions in `client.py`, new `cmd_*` handlers in `nlm.py`, new `SKILL.md` files. The `deduplicate_notebook_sources()` backend function already exists in `client.py`. Tests follow the existing integration-test pattern in `tests/test_cli.py` (real CLI subprocess calls against `/tmp/nlm-test`).

**Tech Stack:** Python 3, `notebooklm` library (Playwright-based), `pytest`, bash SKILL.md files.

---

## File Map

| File | Action | What changes |
|------|--------|-------------|
| `scripts/lib/client.py` | Modify | Add `delete_source()`; modify `add_url()` to return `{"skipped": True, ...}` when URL exists |
| `scripts/nlm.py` | Modify | Modify `cmd_add()` to handle skipped; add `cmd_delete()`, `cmd_deduplicate()`; update router |
| `skills/nlm-add/SKILL.md` | Modify | Document `skipped` response |
| `skills/nlm-delete/SKILL.md` | Create | New skill definition |
| `skills/nlm-deduplicate/SKILL.md` | Create | New skill definition |

---

## Task 1: `client.py` — add `delete_source()` and URL-exists check in `add_url()`

**Files:**
- Modify: `scripts/lib/client.py:127-132` (`add_url`), after line 302 (after `import_research_sources`)

- [ ] **Step 1: Write the failing integration test for `add_url` duplicate detection**

Append to `tests/test_cli.py`:

```python
def test_add_url_skips_duplicate():
    """Adding a URL that already exists should return skipped."""
    # Use a stable URL unlikely to already be in the test notebook
    url = "https://en.wikipedia.org/wiki/Deduplication"
    # First add
    out1 = run(["add", "--url", url, "--project-path", PROJECT])
    assert out1["status"] in ("ok", "skipped")
    # Second add — must be skipped
    out2 = run(["add", "--url", url, "--project-path", PROJECT])
    assert out2["status"] == "skipped"
    assert out2["reason"] == "already_exists"
    assert "source" in out2
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd "/Users/marine/Code/NotebookLM SKILL/marine-notebooklm-skill"
.venv/bin/python -m pytest tests/test_cli.py::test_add_url_skips_duplicate -v
```

Expected: FAIL — `add_url` currently returns `{"status": "ok", ...}` on second call.

- [ ] **Step 3: Modify `add_url()` in `scripts/lib/client.py`**

Replace the existing `add_url` function (lines 127-132):

```python
def add_url(notebook_id: str, url: str) -> dict[str, Any]:
    async def _run():
        async with await NotebookLMClient.from_storage() as client:
            existing = await client.sources.list(notebook_id)
            normalized = url.rstrip("/").lower()
            for s in existing:
                if s.url and s.url.rstrip("/").lower() == normalized:
                    return {"skipped": True, "id": s.id, "title": s.title or url}
            source = await client.sources.add_url(notebook_id, url, wait=True)
            return {"id": source.id, "title": getattr(source, "title", url)}
    return asyncio.run(_run())
```

- [ ] **Step 4: Write the failing test for `delete_source()`**

Append to `tests/test_cli.py`:

```python
def test_delete_source_by_url():
    """Add a URL then delete it by URL."""
    url = "https://en.wikipedia.org/wiki/Source_management"
    # Ensure it exists first
    run(["add", "--url", url, "--project-path", PROJECT])
    out = run(["delete", "--url", url, "--project-path", PROJECT])
    assert out["status"] == "ok"
    assert "deleted" in out
    assert out["deleted"]["id"]


def test_delete_source_not_found():
    """Deleting a URL not in the notebook returns not_found."""
    url = "https://nonexistent-nlm-test-url-xyz.example.com/page"
    out = run(["delete", "--url", url, "--project-path", PROJECT], expect_success=False)
    # exit code non-zero for not_found
```

- [ ] **Step 5: Add `delete_source()` to `scripts/lib/client.py`**

Add after the `add_note` function (after line 148):

```python
def delete_source(notebook_id: str, source_id: str) -> bool:
    """Delete a source by ID. Returns True if deleted."""
    async def _run():
        async with await NotebookLMClient.from_storage() as client:
            return await client.sources.delete(notebook_id, source_id)
    return asyncio.run(_run())
```

- [ ] **Step 6: Commit**

```bash
cd "/Users/marine/Code/NotebookLM SKILL/marine-notebooklm-skill"
git add scripts/lib/client.py tests/test_cli.py
git commit -m "feat(client): add delete_source(); add_url() skips existing URLs"
```

---

## Task 2: `nlm.py` — update `cmd_add()` to handle skipped response

**Files:**
- Modify: `scripts/nlm.py:524-550` (`cmd_add`)

- [ ] **Step 1: Run the `test_add_url_skips_duplicate` test to confirm it now passes from Task 1**

```bash
.venv/bin/python -m pytest tests/test_cli.py::test_add_url_skips_duplicate -v
```

Expected: FAIL still — `cmd_add` doesn't yet check `result.get("skipped")` and emits wrong JSON.

- [ ] **Step 2: Modify `cmd_add()` in `scripts/nlm.py`**

Replace the `if parsed.url:` block (lines 545-547):

```python
    if parsed.url:
        result = client.add_url(notebook_id, parsed.url)
        if result.get("skipped"):
            print(json.dumps({
                "status": "skipped",
                "reason": "already_exists",
                "source": {"id": result["id"], "title": result["title"]},
            }, indent=2, ensure_ascii=False))
        else:
            print(json.dumps({"status": "ok", "type": "url", "source": result}, indent=2, ensure_ascii=False))
```

- [ ] **Step 3: Run tests**

```bash
.venv/bin/python -m pytest tests/test_cli.py::test_add_url_skips_duplicate -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add scripts/nlm.py
git commit -m "feat(nlm): cmd_add outputs skipped status for duplicate URLs"
```

---

## Task 3: `nlm.py` — add `cmd_delete()` and wire router

**Files:**
- Modify: `scripts/nlm.py` — add `cmd_delete()` before `cmd_migrate`, update router

- [ ] **Step 1: Confirm `test_delete_source_by_url` currently fails**

```bash
.venv/bin/python -m pytest tests/test_cli.py::test_delete_source_by_url -v
```

Expected: FAIL — "Unknown command: delete".

- [ ] **Step 2: Add `cmd_delete()` to `scripts/nlm.py`**

Add before `cmd_migrate` (before line 553):

```python
def cmd_delete(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="nlm delete")
    parser.add_argument("--url", help="Delete source matching this URL")
    parser.add_argument("--source-id", help="Delete source with this ID")
    parser.add_argument("--project-path", default=".")
    parsed = parser.parse_args(args)

    if not parsed.url and not parsed.source_id:
        print(json.dumps({"error": "Provide --url or --source-id"}))
        sys.exit(1)

    assert_authenticated()
    project_path = Path(parsed.project_path).expanduser().resolve()
    cfg = load_project_config(project_path)
    notebook_id = _resolve_local_id(cfg)
    if not notebook_id:
        print(json.dumps({"error": "No local notebook configured. Run: nlm setup"}))
        sys.exit(1)

    import lib.client as client
    from notebooklm import NotebookLMClient
    import asyncio

    async def _find_and_delete():
        async with await NotebookLMClient.from_storage() as c:
            sources = await c.sources.list(notebook_id)
            if parsed.source_id:
                match = next((s for s in sources if s.id == parsed.source_id), None)
            else:
                normalized = parsed.url.rstrip("/").lower()
                match = next(
                    (s for s in sources if s.url and s.url.rstrip("/").lower() == normalized),
                    None,
                )
            if not match:
                return None
            await c.sources.delete(notebook_id, match.id)
            return {"id": match.id, "title": match.title}

    deleted = asyncio.run(_find_and_delete())
    if deleted is None:
        key = parsed.url or parsed.source_id
        print(json.dumps({"status": "not_found", "key": key}))
        sys.exit(1)
    print(json.dumps({"status": "ok", "deleted": deleted}, indent=2, ensure_ascii=False))
```

- [ ] **Step 3: Add `delete` to the router**

In the `main()` function, add after the `"add"` branch:

```python
    elif command == "delete":
        cmd_delete(args)
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/python -m pytest tests/test_cli.py::test_delete_source_by_url tests/test_cli.py::test_delete_source_not_found -v
```

Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/nlm.py
git commit -m "feat(nlm): add cmd_delete() — delete sources by URL or ID"
```

---

## Task 4: `nlm.py` — add `cmd_deduplicate()` and wire router

**Files:**
- Modify: `scripts/nlm.py` — add `cmd_deduplicate()`, update router

- [ ] **Step 1: Write the failing integration test**

Append to `tests/test_cli.py`:

```python
def test_deduplicate():
    """nlm deduplicate runs without error and returns ok status."""
    out = run(["deduplicate", "--project-path", PROJECT])
    assert out["status"] == "ok"
    assert "removed" in out
    assert "kept" in out
    assert isinstance(out["removed"], int)
    assert isinstance(out["kept"], int)
```

- [ ] **Step 2: Confirm it fails**

```bash
.venv/bin/python -m pytest tests/test_cli.py::test_deduplicate -v
```

Expected: FAIL — "Unknown command: deduplicate".

- [ ] **Step 3: Add `cmd_deduplicate()` to `scripts/nlm.py`**

Add after `cmd_delete`:

```python
def cmd_deduplicate(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="nlm deduplicate")
    parser.add_argument("--project-path", default=".")
    parsed = parser.parse_args(args)

    assert_authenticated()
    project_path = Path(parsed.project_path).expanduser().resolve()
    cfg = load_project_config(project_path)
    notebook_id = _resolve_local_id(cfg)
    if not notebook_id:
        print(json.dumps({"error": "No local notebook configured. Run: nlm setup"}))
        sys.exit(1)

    import lib.client as client
    result = client.deduplicate_notebook_sources(notebook_id)
    print(json.dumps({"status": "ok", **result}, indent=2, ensure_ascii=False))
```

- [ ] **Step 4: Add `deduplicate` to the router**

```python
    elif command == "deduplicate":
        cmd_deduplicate(args)
```

- [ ] **Step 5: Run tests**

```bash
.venv/bin/python -m pytest tests/test_cli.py::test_deduplicate -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/nlm.py
git commit -m "feat(nlm): add cmd_deduplicate() — manual source deduplication"
```

---

## Task 5: Skill files — create `nlm-delete`, `nlm-deduplicate`, update `nlm-add`

**Files:**
- Create: `skills/nlm-delete/SKILL.md`
- Create: `skills/nlm-deduplicate/SKILL.md`
- Modify: `skills/nlm-add/SKILL.md`

- [ ] **Step 1: Create `skills/nlm-delete/SKILL.md`**

```bash
mkdir -p "/Users/marine/Code/NotebookLM SKILL/marine-notebooklm-skill/skills/nlm-delete"
```

Content:

```markdown
---
name: nlm-delete
description: Delete a source from the project's local NotebookLM notebook by URL or source ID. User-triggered only.
allowed-tools:
  - Bash
---

# nlm-delete

Delete a source from your project's local NotebookLM notebook. User-triggered only — never auto-run.

## Parameters

| Parameter | Values | Default | Description |
|-----------|--------|---------|-------------|
| `--url` | URL | — | Delete source matching this URL (case-insensitive, ignores trailing slash) |
| `--source-id` | string | — | Delete source with this exact ID |
| `--project-path` | path | `$(pwd)` | Project root containing `.nlm/config.json` |

Provide either `--url` or `--source-id`. If neither is given, ask the user which source to delete.

## Usage

```bash
INVOKE="bash $HOME/.claude/skills/nlm/scripts/invoke.sh"

# Delete by URL
$INVOKE delete --url "https://example.com/article"

# Delete by source ID
$INVOKE delete --source-id "abc123xyz"
```

## Output

```json
// Success
{"status": "ok", "deleted": {"id": "...", "title": "..."}}

// Not found
{"status": "not_found", "key": "https://..."}
```

If `not_found`, inform the user the source was not in the notebook.
```

- [ ] **Step 2: Create `skills/nlm-deduplicate/SKILL.md`**

```bash
mkdir -p "/Users/marine/Code/NotebookLM SKILL/marine-notebooklm-skill/skills/nlm-deduplicate"
```

Content:

```markdown
---
name: nlm-deduplicate
description: Remove duplicate URL sources from the project's local NotebookLM notebook. User-triggered only.
allowed-tools:
  - Bash
---

# nlm-deduplicate

Remove duplicate sources from your project's local NotebookLM notebook. Keeps the oldest source per URL and deletes the rest. User-triggered only — never auto-run.

Note: `/nlm-research` already runs deduplication automatically after each import. Use this skill for manual cleanup.

## Parameters

| Parameter | Values | Default | Description |
|-----------|--------|---------|-------------|
| `--project-path` | path | `$(pwd)` | Project root containing `.nlm/config.json` |

## Usage

```bash
INVOKE="bash $HOME/.claude/skills/nlm/scripts/invoke.sh"
$INVOKE deduplicate --project-path "."
```

## Output

```json
{"status": "ok", "removed": 3, "kept": 12}
```

If `removed` is 0, tell the user "笔记本来源无重复，无需清理。"
```

- [ ] **Step 3: Update `skills/nlm-add/SKILL.md`** — add `skipped` response documentation

Replace current content:

```markdown
---
name: nlm-add
description: Manually add a URL source or text note to the project's local NotebookLM notebook. User-triggered only.
allowed-tools:
  - Bash
---

# nlm-add

Add a URL or text note to your project's local NotebookLM notebook. User-triggered only — never auto-run.

## Parameters

| Parameter | Values | Default | Description |
|-----------|--------|---------|-------------|
| `--url` | URL | — | Web page to add as a source |
| `--note` | text | — | Text content to save as a note |
| `--title` | text | `"Note"` | Title for the note (only with `--note`) |
| `--project-path` | path | `$(pwd)` | Project root containing `.nlm/config.json` |

Provide either `--url` or `--note`. If neither is given, ask the user: "Add a URL or a text note? Please provide the content."

## Usage

```bash
INVOKE="bash $HOME/.claude/skills/nlm/scripts/invoke.sh"

# Add a web URL
$INVOKE add --url "<URL>"

# Add a text note
$INVOKE add --note "<content>" --title "<title>"
```

## Output

```json
// URL added successfully
{"status": "ok", "type": "url", "source": {"id": "...", "title": "..."}}

// URL already exists in notebook (silently skipped)
{"status": "skipped", "reason": "already_exists", "source": {"id": "...", "title": "..."}}

// Note added successfully
{"status": "ok", "type": "note", "note": {"id": "...", "title": "..."}}
```

If `status` is `skipped`, inform the user the URL is already in the notebook — no action needed.
```

- [ ] **Step 4: Commit skill files**

```bash
cd "/Users/marine/Code/NotebookLM SKILL/marine-notebooklm-skill"
git add skills/nlm-delete/SKILL.md skills/nlm-deduplicate/SKILL.md skills/nlm-add/SKILL.md
git commit -m "feat(skills): add nlm-delete, nlm-deduplicate; update nlm-add with skipped response"
```

---

## Task 6: Deploy to `~/.claude/skills/` and verify

**Files:** Deployed copies at `~/.claude/skills/`

- [ ] **Step 1: Sync scripts and skills**

```bash
rsync -av --delete "/Users/marine/Code/NotebookLM SKILL/marine-notebooklm-skill/scripts/" ~/.claude/skills/nlm/scripts/
rsync -av --delete "/Users/marine/Code/NotebookLM SKILL/marine-notebooklm-skill/skills/" ~/.claude/skills/nlm/skills/

for skill in nlm-add nlm-delete nlm-deduplicate; do
  mkdir -p ~/.claude/skills/$skill
  cp "/Users/marine/Code/NotebookLM SKILL/marine-notebooklm-skill/skills/$skill/SKILL.md" ~/.claude/skills/$skill/SKILL.md
done
```

- [ ] **Step 2: Verify skill files deployed**

```bash
ls ~/.claude/skills/nlm-delete/
ls ~/.claude/skills/nlm-deduplicate/
```

Expected: each directory contains `SKILL.md`.

- [ ] **Step 3: Smoke-test deduplicate against the test project**

```bash
bash ~/.claude/skills/nlm/scripts/invoke.sh deduplicate --project-path /tmp/nlm-test
```

Expected: `{"status": "ok", "removed": ..., "kept": ...}` with exit code 0.

- [ ] **Step 4: Commit deploy verification note (no-op — nothing to stage)**

All done. Confirm with the user that the three new capabilities are working.
