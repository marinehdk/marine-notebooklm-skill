---
name: nlm-migrate
description: Migrate valuable universal knowledge from a project notebook to a global domain notebook. User-triggered only, requires explicit confirmation.
allowed-tools:
  - Bash
---

# nlm-migrate

```bash
INVOKE="bash $HOME/.claude/skills/nlm/scripts/invoke.sh"
$INVOKE migrate --content "<knowledge text>" --target-global "<domain>" --title "<title>"
```

Always confirm with user before running. Show what will be written and to which global notebook.
