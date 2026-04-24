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
