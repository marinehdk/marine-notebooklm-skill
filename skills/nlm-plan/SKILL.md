---
name: nlm-plan
description: Compare technical options using NotebookLM evidence. Use when user is choosing between 2+ approaches, libraries, or architectures.
allowed-tools:
  - Bash
---

# nlm-plan

Compare technical options using evidence from your NotebookLM notebook. Auto-triggered when user evaluates 2+ choices. Produces a 1–5 numeric score matrix with composite scores and automatic research escalation.

## Parameters

| Parameter | Values | Default | Description |
|-----------|--------|---------|-------------|
| `--question` | text | required | The decision being evaluated |
| `--options` | `"A,B,C"` | required | Comma-separated options to compare |
| `--criteria` | `"x,y,z"` | optional | Comma-separated evaluation criteria (auto-proposed if omitted) |
| `--max-research` | integer | `3` | Max research calls allowed (fast + deep each count as 1) |
| `--project-path` | path | `$(pwd)` | Project root containing `.nlm/config.json` |

If options or question are missing, ask the user before running.

## Usage

```bash
INVOKE="$HOME/.claude/skills/nlm/scripts/invoke.sh"
bash $INVOKE plan --question "<decision>" --options "A,B" --criteria "performance,maintainability"
```

## Output

```json
{
  "recommendation": "Option A",
  "composite_scores": {"Option A": 4.2, "Option B": 3.0},
  "matrix": {
    "Option A": {
      "performance": {"score": 5, "reasoning": "..."},
      "cost": {"score": 3, "reasoning": "...", "evidence_gap": true}
    },
    "Option B": {
      "performance": {"score": 3, "reasoning": "..."},
      "cost": {"score": 2, "reasoning": "...", "parse_warning": true}
    }
  },
  "rationale": "Option A scored highest overall (4.2 vs 3.0)...",
  "research_used": 2,
  "max_research": 3,
  "evidence_gaps": ["Option B / cost"]
}
```

Present `recommendation` with `rationale`. Show `matrix` as a comparison table. Note any `evidence_gaps` for the user to investigate further.

## Score scale

| Score | Meaning |
|-------|---------|
| 5 | Excellent |
| 4 | Good |
| 3 | Average |
| 2 | Below average |
| 1 | Poor |

## Research escalation

When notebook evidence confidence is low for an option, `nlm-plan` automatically runs research (fast → deep if fast confidence is still low). `research_used` shows calls made; `evidence_gaps` lists option/criterion pairs uncovered within `--max-research`.

## Field reference

| Field | Always present | Description |
|-------|---------------|-------------|
| `recommendation` | ✅ | Option with highest composite score |
| `composite_scores` | ✅ | Per-option mean of valid scores (1 decimal) |
| `matrix` | ✅ | Per-option, per-criterion scores and reasoning |
| `rationale` | ✅ | One-sentence justification for recommendation |
| `research_used` | ✅ | Number of research calls made |
| `max_research` | ✅ | The `--max-research` cap used |
| `evidence_gaps` | ✅ | List of `"option / criterion"` pairs with no evidence |
| `evidence_gap` | On matrix entry | Research cap exhausted before covering this pair |
| `parse_warning` | On matrix entry | Score format not parseable; score=null |
