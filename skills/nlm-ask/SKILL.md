---
name: nlm-ask
description: Query NotebookLM notebooks for grounded answers. Use when user asks about concepts, APIs, architecture patterns, or domain knowledge. Triggered by main session Claude or background Agent — both call via bash invoke.
allowed-tools:
  - Bash
---

# nlm-ask

Query your NotebookLM notebook(s) for grounded answers. **Never imports sources** — read-only. Triggered by main session or background Agent identically.

## Parameters

| Parameter | Values | Default | Description |
|-----------|--------|---------|-------------|
| `--question` | text | required | The question to ask |
| `--scope` | `auto\|local\|global\|synthesis\|domain:<key>` | `auto` | Query routing target |
| `--on-low-confidence` | `prompt\|research\|silent` | `prompt` | `research` = auto fast-research + retry; `prompt` = attach hint; `silent` = return as-is |
| `--format` | `json\|text` | `json` | Output format |
| `--project-path` | path | `$(pwd)` | Project root containing `.nlm/config.json` |

### `--scope` routing

| Value | Behavior |
|-------|----------|
| `auto` | Classify question → domain notebook first → local → global → synthesis |
| `local` | Project local notebook only |
| `global` | Route among global notebooks via Haiku ranking |
| `synthesis` | Cross-domain synthesis (META) notebook only |
| `domain:<key>` | Specific domain notebook, fallback to local on low confidence |

## Usage

```bash
INVOKE="$HOME/.claude/skills/nlm/scripts/invoke.sh"
bash $INVOKE ask --question "<question>" --scope auto --project-path "."
```

## Output

```json
{
  "answer": "...",
  "confidence": "high|medium|low|not_found",
  "answered_by": ["domain:navigation_algorithms", "local"],
  "source_notebook": "domain:navigation_algorithms",
  "citations": [{"citation_number": 1, "text": "..."}],
  "suggest_research": false,
  "next_action": {
    "type": "suggest_research",
    "message": "...",
    "command": "nlm research --topic \"...\" --add-sources --project-path \".\""
  }
}
```

- `answered_by`: list of notebooks that contributed (most specific first)
- `suggest_research`: `true` when confidence is `low` or `not_found` — caller should surface `/nlm-research`
- `next_action`: only present when `--on-low-confidence prompt` and confidence is low

## Auto-trigger rules

Call `nlm ask --scope auto` when encountering uncertainty about:
- Domain-specific concepts (algorithms, specs, standards)
- Architecture decisions documented in notebooks
- Technical terms not answerable from code alone

**Do NOT call for:** general programming syntax, public API docs, anything answerable from the current repo.

## Handling results

| confidence | `suggest_research` | Action |
|------------|-------------------|--------|
| `high` / `medium` | `false` | Use answer directly |
| `auto_researched: true` | `false` | Sources were auto-imported; use directly |
| `low` / `not_found` | `true` | Surface to user; offer `/nlm-research` for accumulation |
