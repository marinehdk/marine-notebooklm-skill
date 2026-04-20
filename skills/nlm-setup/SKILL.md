---
name: nlm-setup
description: Initialize a project's NotebookLM configuration or authenticate with Google. Run once per project.
allowed-tools:
  - Bash
---

# nlm-setup

```bash
INVOKE="bash $HOME/.claude/skills/nlm/scripts/invoke.sh"

# Auth only
$INVOKE setup --auth

# Full setup (lists notebooks, then re-invoke with chosen ID)
$INVOKE setup --project-path "."
$INVOKE setup --project-path "." --notebook-id "<uuid>"

# Create new notebook
$INVOKE setup --project-path "." --create "Title"
```
