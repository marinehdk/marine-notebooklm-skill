---
name: nlm-ask
description: Query NotebookLM notebooks. Use when user asks about concepts, APIs, architecture patterns, or domain knowledge that might be in their curated notebook sources.
allowed-tools:
  - Bash
---

# nlm-ask

```bash
INVOKE="bash $HOME/.claude/skills/nlm/scripts/invoke.sh"
$INVOKE ask --question "<question>" --project-path "." --scope auto --format json
```

Interpret the JSON output: use `answer` if confidence is `high`/`medium`. If `low`/`not_found`, tell the user and suggest running `/nlm-research`.
