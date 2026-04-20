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
$INVOKE add --url "<URL>" --project-path "$(pwd)"

# Add a text note
$INVOKE add --note "<content>" --title "<title>" --project-path "$(pwd)"
```
