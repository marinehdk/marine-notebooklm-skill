---
name: nlm-plan
description: Compare technical options using NotebookLM evidence. Use when user is choosing between 2+ approaches, libraries, or architectures.
allowed-tools:
  - Bash
---

# nlm-plan

Compare technical options using evidence from your NotebookLM notebook. Auto-triggered when user evaluates 2+ choices.

## Parameters

| Parameter | Values | Default | Description |
|-----------|--------|---------|-------------|
| `--question` | text | required | The decision being evaluated |
| `--options` | `"A,B,C"` | required | Comma-separated options to compare |
| `--criteria` | `"x,y,z"` | optional | Comma-separated evaluation criteria |
| `--project-path` | path | `$(pwd)` | Project root containing `.nlm/config.json` |

If options or question are missing, ask the user before running.

## Usage

```bash
INVOKE="bash $HOME/.claude/skills/nlm/scripts/invoke.sh"
$INVOKE plan --question "<decision>" --options "A,B" --criteria "performance,maintainability"
```

## Output

```json
{
  "recommendation": "Option A",
  "rationale": "Based on notebook evidence...",
  "matrix": {
    "Option A": {"performance": "high", "maintainability": "medium"},
    "Option B": {"performance": "medium", "maintainability": "high"}
  }
}
```

Present `recommendation` with `rationale`. Show `matrix` as a comparison table.
