---
name: nlm-deduplicate
description: Remove duplicate URL sources from a NotebookLM notebook. User-triggered only.
allowed-tools:
  - Bash
---

# nlm-deduplicate

Remove duplicate sources from a NotebookLM notebook. Keeps the oldest source per URL and deletes the rest. User-triggered only — never auto-run.

Note: `/nlm-research` already runs deduplication automatically after each import. Use this skill for manual cleanup.

## Parameters

| Parameter | Values | Default | Description |
|-----------|--------|---------|-------------|
| `--notebook-id` | UUID | — | Target notebook directly by ID (overrides `--project-path`) |
| `--project-path` | path | `$(pwd)` | Project root containing `.nlm/config.json` |

Provide either `--notebook-id` or `--project-path`. If both omitted, defaults to current directory.

## Usage

```bash
INVOKE="bash $HOME/.claude/skills/nlm/scripts/invoke.sh"

# Deduplicate current project's notebook
$INVOKE deduplicate --project-path "."

# Deduplicate any notebook by ID (no project config needed)
$INVOKE deduplicate --notebook-id "6c20d15e-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
```

## Output

```json
{"status": "ok", "notebook_id": "6c20d15e-...", "removed": 3, "failed_removed": 5, "kept": 12}
```

- `removed` — duplicate URL sources deleted
- `failed_removed` — error/failed sources deleted
- `kept` — sources remaining after cleanup

If both `removed` and `failed_removed` are 0, tell the user "笔记本来源无重复且无失败来源，无需清理。"
