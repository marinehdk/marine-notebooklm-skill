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
| `--depth` | `fast\|deep` | `fast` | `fast` = 60s timeout; `deep` = 600s timeout |
| `--add-sources` / `--no-add-sources` | flag | `--add-sources` | Whether to import found URLs into the local notebook |
| `--max-import` | integer | `10` | Max sources to import per run (fast returns ~10, deep returns ~50). Pass `0` to skip import entirely. |
| `--project-path` | path | `$(pwd)` | Project root containing `.nlm/config.json` |

## Auto-trigger rule

Always use `--add-sources` (the default). Sources are automatically imported up to `--max-import` (default 5 for fast, 3 for deep). Use `--no-add-sources` or `--max-import 0` only for read-only lookups with no intent to save results.

Notebook capacity is capped at 300 sources. When the notebook reaches 290, import is automatically blocked with a `capacity_warning` and a prompt to run `/nlm-deduplicate`.

## Usage

```bash
INVOKE="$HOME/.claude/skills/nlm/scripts/invoke.sh"
bash $INVOKE research --topic "<topic>" --depth fast --project-path "."
```

Research takes 30–120s. Present the `report`, list `sources`, and note how many were imported (`sources_imported`).
