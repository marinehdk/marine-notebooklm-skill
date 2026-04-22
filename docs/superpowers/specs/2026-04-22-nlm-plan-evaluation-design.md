# nlm-plan Evaluation Overhaul — Design Spec

**Date:** 2026-04-22  
**Status:** Approved  
**Scope:** `scripts/nlm.py` (`cmd_plan`), `scripts/lib/` (new `plan_evaluator.py`), `skills/nlm-plan/SKILL.md`

---

## Problem

The current `cmd_plan` evaluation is unreliable:

1. **Fragile scoring** — extracts high/medium/low by keyword search in free-form answer text
2. **No confidence tracking** — ignores existing `AnswerAnalyzer`, `route_notebooks`, `handle_confidence`
3. **No research escalation** — no fallback when notebook evidence is thin
4. **Single notebook** — always uses `notebook_ids[0]`, ignores scope routing
5. **Score = count of "high"** — recommendation is arbitrary

---

## Goal

Produce an objective, quantified, evidence-grounded comparison matrix with:
- 1–5 numeric scores per option × criterion
- Equal-weight composite score per option
- Automatic research escalation when evidence confidence is low
- Transparent evidence gaps when research cap is exhausted

---

## New CLI Parameter

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--max-research` | `3` | Total research calls allowed per plan invocation (fast + deep each count as 1) |

Existing parameters unchanged: `--question`, `--options`, `--criteria`, `--project-path`.

---

## Four-Phase Flow

### Phase 1: Evidence Collection

For every `(option, criterion)` pair, call `client.ask()` with a focused query:

```
"Evidence for option '{option}' on criterion '{criterion}': {question}"
```

- Use `route_notebooks()` + `_resolve_local_id()` / `_resolve_global_ids()` for proper scope routing (mirrors `cmd_ask` auto-scope logic)
- Run `AnswerAnalyzer.assess(answer)` on each response
- Tag pairs with `confidence ∈ {low, not_found}` as **evidence gaps** needing Phase 2

### Phase 2: Research Escalation

Group evidence gaps by option. For each option with gaps:

1. Construct topic: `"{question} — focus on option '{option}'"`
2. Call `client.research(notebook_id, topic, mode="fast")`
3. Assess result with `AnswerAnalyzer.assess(report)`
4. If confidence still `low` / `not_found` → call again with `mode="deep"` (consumes a second counter slot)
5. Decrement global research counter after each call
6. If counter reaches 0: mark remaining gaps as `evidence_gap=true` and continue without blocking

**Counter rules:**
- `--max-research 3` (default): a single option can consume 2 slots (fast + deep), leaving 1 for another option
- fast → deep upgrade only when `AnswerAnalyzer` reports low confidence on the fast report

### Phase 3: Structured Scoring

For each `(option, criterion)`, one dedicated `client.ask()` call. The Phase 1 answer and (if available) Phase 2 research report are **embedded in the question text** so NotebookLM scores against both the injected evidence and its own notebook knowledge. No sources are added to the notebook (consistent with auto-trigger rules).

Prompt template:
```
Evidence gathered about '{option}' on '{criterion}':
---
{phase1_answer}
{phase2_report if research_used else ""}
---
Based on the above evidence and your notebook knowledge, score option '{option}'
on criterion '{criterion}' from 1 to 5 where:
  1 = poor  2 = below average  3 = average  4 = good  5 = excellent
Output format (exactly):
SCORE: N
REASONING: one sentence
```

- Parse with regex `SCORE:\s*([1-5])`
- On parse failure: `score = null`, `parse_warning = true`, excluded from composite mean
- On `evidence_gap = true`: score skipped, gap preserved in output

### Phase 4: Aggregation

- `composite_score[option]` = mean of valid (non-null) criterion scores, rounded to 1 decimal
- `recommendation` = option with highest composite score
- `rationale` = one final `client.ask()` synthesising the top option's reasoning across all scored criteria

---

## Output Format

```json
{
  "recommendation": "Option A",
  "composite_scores": {
    "Option A": 4.2,
    "Option B": 3.0
  },
  "matrix": {
    "Option A": {
      "performance": {"score": 5, "reasoning": "..."},
      "cost":        {"score": 3, "reasoning": "...", "evidence_gap": true}
    },
    "Option B": {
      "performance": {"score": 3, "reasoning": "..."},
      "cost":        {"score": 2, "reasoning": "...", "parse_warning": true}
    }
  },
  "rationale": "Option A scored highest overall (4.2 vs 3.0)...",
  "research_used": 2,
  "max_research": 3,
  "evidence_gaps": ["Option B / cost"]
}
```

**Field rules:**
- `composite_scores`: only valid scores (non-null) contribute to the mean
- `evidence_gaps`: list of `"{option} / {criterion}"` strings for gaps not resolved by research
- `parse_warning`: appears only on individual matrix entries where score parsing failed
- `evidence_gap`: appears only on individual matrix entries where research cap was exhausted before covering that pair

---

## Internal Data Structures

Defined in new `scripts/lib/plan_evaluator.py`:

```python
@dataclass
class CriterionEvidence:
    option: str
    criterion: str
    answer: str
    confidence: str          # "high" | "medium" | "low" | "not_found"
    source: str              # "local" | "global"
    research_used: bool

@dataclass
class CriterionScore:
    option: str
    criterion: str
    score: int | None        # 1-5, None if parse failed or evidence_gap
    reasoning: str
    evidence_gap: bool
    parse_warning: bool
```

---

## Changes Required

| File | Change |
|------|--------|
| `scripts/nlm.py` | Rewrite `cmd_plan`: add `--max-research` arg, call `PlanEvaluator` |
| `scripts/lib/plan_evaluator.py` | New file: `PlanEvaluator` class encapsulating all 4 phases |
| `skills/nlm-plan/SKILL.md` | Update output format, add `--max-research` param docs |

`cmd_plan` in `nlm.py` becomes a thin dispatcher: parse args → call `PlanEvaluator` → print JSON. All logic lives in `plan_evaluator.py`.

---

## Constraints & Edge Cases

- **No criteria passed**: ask NotebookLM to propose criteria for the question, then proceed normally
- **Single option**: return single-option matrix with composite score, no recommendation needed
- **All evidence gaps**: output matrix with all nulls, `evidence_gaps` lists all pairs, suggest running `nlm-research --add-sources` manually
- **max-research = 0**: skip Phase 2 entirely, all low-confidence pairs become `evidence_gap=true`
