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
| `--notebook-list` | flag | — | List all notebooks and select one for this project |
| `--notebook-id` | UUID | — | Bind a specific notebook ID directly |
| `--create` | title | — | Create a new notebook and bind it |
| `--project-path` | path | current dir | Only needed when configuring a different project |

## Usage

```bash
INVOKE="bash $HOME/.claude/skills/nlm/scripts/invoke.sh"

# Show current project status (auth + bound notebook)
$INVOKE setup

# Authenticate (opens real Chrome browser for Google login)
$INVOKE setup --auth

# Re-authenticate (clears saved session)
$INVOKE setup --reauth

# List notebooks and pick one for this project
$INVOKE setup --notebook-list

# Bind a specific notebook
$INVOKE setup --notebook-id "<uuid>"

# Create new notebook and bind it
$INVOKE setup --create "Title"

# Configure a different project directory
$INVOKE setup --notebook-id "<uuid>" --project-path "/path/to/project"
```

## Workflow

1. `--auth` → authenticate once
2. `--notebook-list` → list notebooks, note the UUID you want
3. `--notebook-id <uuid>` → bind it to this project
