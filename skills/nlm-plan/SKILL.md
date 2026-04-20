---
name: nlm-plan
description: Compare technical options using NotebookLM evidence. Use when user is choosing between 2+ approaches, libraries, or architectures.
allowed-tools:
  - Bash
---

# nlm-plan

```bash
INVOKE="bash $HOME/.claude/skills/nlm/scripts/invoke.sh"
$INVOKE plan --question "<decision>" --options "A,B" [--criteria "x,y"] --project-path "." 
```

Present `recommendation` with `rationale`. Show `matrix` as a comparison table.
