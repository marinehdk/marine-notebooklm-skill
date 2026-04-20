---
name: nlm-ask
description: Query NotebookLM notebooks. Use when user asks about concepts, APIs, architecture patterns, or domain knowledge that might be in their curated notebook sources.
allowed-tools:
  - Bash
---

# nlm-ask

Query your NotebookLM notebook for grounded answers. Auto-triggered when Claude encounters knowledge uncertainty.

## Parameters

| Parameter | Values | Default | Description |
|-----------|--------|---------|-------------|
| `--question` | text | required | The question to ask |
| `--scope` | `auto\|local\|global` | `auto` | `auto` = local first, fallback to global; `local` = project only; `global` = domain notebooks only |
| `--format` | `json\|text` | `json` | Output format |
| `--project-path` | path | `$(pwd)` | Project root containing `.nlm/config.json` |

## Usage

```bash
INVOKE="bash $HOME/.claude/skills/nlm/scripts/invoke.sh"
$INVOKE ask --question "<question>" --scope auto --format json
```

## Output

```json
{
  "answer": "...",
  "confidence": "high|medium|low|not_found",
  "source_notebook": "local|global",
  "citations": [{"citation_number": 1, "text": "..."}]
}
```

## Confidence handling

| Level | Action |
|-------|--------|
| `high` / `medium` | Use the answer directly |
| `low` | Use with caution, tell user to verify |
| `not_found` | Tell user notebook has no relevant content; suggest `/nlm-research` |
