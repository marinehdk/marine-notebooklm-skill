---
name: nlm-migrate
description: Migrate valuable universal knowledge from a project notebook to a global domain notebook. User-triggered only, requires explicit confirmation.
allowed-tools:
  - Bash
---

# nlm-migrate

Promote reusable domain knowledge from the project notebook to a shared global notebook. User-triggered only — always confirm before running.

## Parameters

| Parameter | Values | Default | Description |
|-----------|--------|---------|-------------|
| `--content` | text | required | The knowledge text to migrate |
| `--target-global` | domain name | required | Name of the target global notebook (e.g. `backend-patterns`) |
| `--title` | text | `"Migrated Knowledge"` | Title for the migrated entry |

Before running, show the user what will be written and to which global notebook, and ask for confirmation.

## Usage

```bash
INVOKE="$HOME/.claude/skills/nlm/scripts/invoke.sh"
bash $INVOKE migrate --content "<knowledge text>" --target-global "<domain>" --title "<title>"
```

## Available global notebooks

Run `bash $HOME/.claude/skills/nlm/scripts/invoke.sh setup` to list configured global notebooks.
