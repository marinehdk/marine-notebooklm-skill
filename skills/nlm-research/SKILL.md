---
name: nlm-research
description: Deep research via NotebookLM. Use for parallel subagent research dispatch (--no-add-sources) or user-requested research with source import (--add-sources).
allowed-tools:
  - Bash
---

# nlm-research

Trigger NotebookLM's research feature for a topic. Returns a report and source URLs.

## Parameters

| Parameter | Values | Default | Description |
|-----------|--------|---------|-------------|
| `--topic` | text | required | Research topic |
| `--depth` | `fast\|deep` | `fast` | `fast` = 60s timeout; `deep` = 180s timeout |
| `--add-sources` / `--no-add-sources` | flag | `--add-sources` | Whether to import found URLs into the local notebook |
| `--project-path` | path | `$(pwd)` | Project root containing `.nlm/config.json` |

## Auto-trigger rule

- `--no-add-sources`: may be auto-triggered for parallel subagent research (read-only, no side effects)
- `--add-sources`: **user-triggered only** — always confirm before running as it writes to the notebook

## Usage

**Read-only (parallel subagent / auto-trigger):**
```bash
INVOKE="bash $HOME/.claude/skills/nlm/scripts/invoke.sh"
$INVOKE research --topic "<topic>" --depth fast --no-add-sources --project-path "$(pwd)"
```

**With import (user-triggered only):**
```bash
$INVOKE research --topic "<topic>" --depth fast --add-sources --project-path "$(pwd)"
```

Research takes 30–120s. Present the `report` and list `sources`.
