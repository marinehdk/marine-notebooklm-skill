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
