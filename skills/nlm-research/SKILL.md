---
name: nlm-research
description: Deep research via NotebookLM. Use for parallel subagent research dispatch (--no-add-sources) or user-requested research with source import (--add-sources).
allowed-tools:
  - Bash
---

# nlm-research

**Read-only (parallel subagent use):**
```bash
INVOKE="bash $HOME/.claude/skills/nlm/scripts/invoke.sh"
$INVOKE research --topic "<topic>" --depth fast|deep --no-add-sources --project-path "."
```

**With import (user-triggered only):**
```bash
$INVOKE research --topic "<topic>" --depth fast --add-sources --project-path "."
```

Research takes 30–120s. Return `report` to caller.
