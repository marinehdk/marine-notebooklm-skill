---
name: nlm-add
description: Manually add a URL source or text note to the project's local NotebookLM notebook. User-triggered only.
allowed-tools:
  - Bash
---

# nlm-add

```bash
INVOKE="bash $HOME/.claude/skills/nlm/scripts/invoke.sh"
$INVOKE add --url "<URL>" --project-path "."
$INVOKE add --note "<content>" --title "<title>" --project-path "."
```
