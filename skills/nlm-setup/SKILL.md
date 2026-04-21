---
name: nlm-setup
description: Initialize a project's NotebookLM configuration or authenticate with Google. Run once per project.
allowed-tools:
  - Bash
---

# nlm-setup

Initialize or inspect NotebookLM configuration for the current project.

## Parameters

| Parameter | Values | Default | Description |
|-----------|--------|---------|-------------|
| `--auth` | flag | — | Open Chrome browser to authenticate with Google |
| `--reauth` | flag | — | Clear saved session and re-authenticate |
| `--notebook-list` | flag | — | List recently modified notebooks and select one for this project |
| `--refresh` | flag | — | Force refresh notebook list from API (bypass 24h cache) |
| `--notebook-id` | UUID | — | Bind a specific notebook ID directly |
| `--create` | title | — | Create a new notebook and bind it |
| `--project-path` | path | current dir | Only needed when configuring a different project |

## Caching

Notebook list is cached locally for 24 hours in `~/.nlm/notebooks_cache.json` to avoid repeated API calls. Use `--refresh` to force a fresh fetch from NotebookLM.

## Usage

```bash
INVOKE="bash $HOME/.claude/skills/nlm/scripts/invoke.sh"

# Show current project status (auth + bound notebook)
$INVOKE setup

# Authenticate (opens real Chrome browser for Google login)
$INVOKE setup --auth

# Re-authenticate (clears saved session)
$INVOKE setup --reauth

# List 10 most recently modified notebooks and pick one for this project
$INVOKE setup --notebook-list

# Force refresh notebook list from API
$INVOKE setup --notebook-list --refresh

# Bind a specific notebook
$INVOKE setup --notebook-id "<uuid>"

# Create new notebook and bind it
$INVOKE setup --create "Title"

# Configure a different project directory
$INVOKE setup --notebook-id "<uuid>" --project-path "/path/to/project"
```

## Output format

When listing notebooks, the output includes a `table` array (10 most recent, sorted by modification time) and a `total` count:

```json
{
  "action": "select_notebook",
  "message": "Re-run with --notebook-id <id> to bind this project",
  "cache": { "cached": true, "cached_at": ... },
  "total": 36,
  "table": [
    { "#": 1, "UUID": "...", "Source": 52, "Title": "船舶流体力学与运动控制讲义", "Modified": "2026-04-20 16:17:18" },
    ...
  ],
  "notebooks": [...]
}
```

## Workflow

1. `--auth` → authenticate once (done)
2. `--notebook-list` → list 10 most recently modified notebooks, note the UUID you want
3. `--notebook-id <uuid>` → bind it to this project
