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

Always use `--add-sources` (the default). Sources are automatically imported into the local notebook — no user confirmation needed. Use `--no-add-sources` only when explicitly doing a read-only lookup with no intent to save results.

## Usage

```bash
INVOKE="bash $HOME/.claude/skills/nlm/scripts/invoke.sh"
$INVOKE research --topic "<topic>" --depth fast --project-path "."
```

Research takes 30–120s. Present the `report`, list `sources`, and note how many were imported (`sources_imported`).
