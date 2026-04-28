---
name: nlm-research
description: Deep research via NotebookLM. Researches a topic AND deposits sources into the correct notebook. Use for parallel subagent research (--no-add-sources) or user-requested research with knowledge accumulation (--add-sources). Triggered by main session or background Agent identically.
allowed-tools:
  - Bash
---

# nlm-research

Trigger NotebookLM's research feature for a topic. Returns a report and routes sources to the correct notebook automatically.

## Parameters

| Parameter | Values | Default | Description |
|-----------|--------|---------|-------------|
| `--topic` | text | required | Research topic |
| `--depth` | `fast\|deep` | `fast` | `fast` = 60s timeout; `deep` = 600s timeout |
| `--target` | `auto\|local\|synthesis\|domain:<key>` | `auto` | Target notebook for source import |
| `--add-sources` / `--no-add-sources` | flag | `--add-sources` | Whether to import found sources into target notebook |
| `--max-import` | integer | none (all) | Hard cap on sources imported this run |
| `--min-relevance` | float | `0.1` | Sources below this threshold are pruned after import |
| `--project-path` | path | `$(pwd)` | Project root containing `.nlm/config.json` |

### `--target` routing

| Value | Behavior |
|-------|----------|
| `auto` | Classify topic → route to matching domain notebook; if no match → local; if new domain suggested → route to local + output `domain_suggestion` |
| `local` | Project local notebook (default fallback) |
| `synthesis` | Cross-domain synthesis notebook |
| `domain:<key>` | Specific domain notebook by key |

## Source management strategy

1. **Domain routing** — `--target auto` classifies topic against domain keyword profiles; routes to best match
2. **New domain advisory** — when topic doesn't match any domain, outputs `domain_suggestion` with a `nlm setup --create-domain` command; routes to local for this run
3. **Cite-filtered import** — only cited sources from report bibliography are imported; falls back to all sources when no bibliography
4. **Dedup + clean** — duplicate URLs and failed imports removed after import
5. **Score + prune** — imported sources scored against topic profile; below `--min-relevance` are deleted
6. **Distillation trigger** — when target notebook exceeds 270 sources, outputs `new_notebook_suggestion`
7. **Domain guard checks** — after import, outputs `merge_suggestions` and `split_suggestions` if domain balance is off

## Usage

```bash
INVOKE="$HOME/.claude/skills/nlm/scripts/invoke.sh"

# Knowledge accumulation (write sources to correct notebook)
bash $INVOKE research --topic "<topic>" --depth fast --project-path "."

# Read-only research (no source import)
bash $INVOKE research --topic "<topic>" --no-add-sources --project-path "."

# Explicit domain routing
bash $INVOKE research --topic "<topic>" --target domain:navigation_algorithms --project-path "."
```

## Output

```json
{
  "status": "ok",
  "topic": "...",
  "target_notebook": "domain:navigation_algorithms",
  "report": "...",
  "sources": [...],
  "sources_cited_count": 5,
  "sources_imported": 5,
  "sources_pruned": 1,
  "duplicates_removed": 0,
  "notebook_source_count": 53,
  "add_sources": true,
  "domain_suggestion": {
    "type": "new_domain_suggested",
    "suggested_name": "Propulsion Systems",
    "message": "..."
  },
  "merge_suggestions": [
    {"merge_from": "regulations_imo", "merge_into": "maritime_regulations", "overlap": 0.45, "command": "..."}
  ],
  "split_suggestions": [],
  "new_notebook_suggestion": "..."
}
```

## Auto-trigger rule

Use `--add-sources` (default) when user intends knowledge accumulation. Use `--no-add-sources` only for read-only lookups (e.g., parallel subagent dispatch with no intent to save results).

When `domain_suggestion` is present in output: surface it to the user and offer the `nlm setup --create-domain` command.
