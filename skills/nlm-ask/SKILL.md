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
| `--scope` | `auto\|local\|global` | `auto` | `auto` = local first, then route among globals; `local` = project notebook only; `global` = route among global notebooks |
| `--on-low-confidence` | `prompt\|research\|silent` | `research` | `research` = auto fast-research, import sources, retry; `prompt` = attach hint only; `silent` = return as-is |
| `--format` | `json\|text` | `json` | Output format |
| `--project-path` | path | `$(pwd)` | Project root containing `.nlm/config.json` |

## Usage

```bash
INVOKE="bash $HOME/.claude/skills/nlm/scripts/invoke.sh"
$INVOKE ask --question "<question>" --scope auto --on-low-confidence research --format json
```

## Output

```json
{
  "answer": "...",
  "confidence": "high|medium|low|not_found",
  "source_notebook": "local|global",
  "citations": [{"citation_number": 1, "text": "..."}],
  "next_action": {
    "type": "suggest_research",
    "message": "...",
    "command": "nlm research --topic \"...\" --add-sources --project-path \".\""
  }
}
```

`next_action` is only present when `confidence` is `low` or `not_found` and `--on-low-confidence` is `prompt` (the default).

## Auto-trigger

Call `nlm ask` when you encounter uncertainty about:
- Domain-specific concepts in this project (algorithms, specs, standards)
- Architecture decisions or design patterns documented in notebooks
- Technical terms you cannot confidently answer from the codebase alone

Do NOT call for: general programming questions, public API docs,
syntax questions, or anything answerable from code in the current repo.

## Handling results

| confidence | `auto_researched` | `next_action` present? | Action |
|------------|-------------------|------------------------|--------|
| `high` / `medium` | — | No | Use answer directly |
| any | `true` | No | Sources were auto-imported and answer reflects newly added content; use directly |
| `low` / `not_found` | — | Yes (`suggest_research`) | Auto-research ran but still low confidence; tell user and offer manual follow-up |
