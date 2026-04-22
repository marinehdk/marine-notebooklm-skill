# nlm-plan Evaluation Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the brittle keyword-heuristic evaluation in `cmd_plan` with a four-phase pipeline (evidence → research escalation → structured 1-5 scoring → composite aggregation).

**Architecture:** A new `PlanEvaluator` class in `scripts/lib/plan_evaluator.py` encapsulates all four phases; `cmd_plan` in `scripts/nlm.py` becomes a thin arg-parser that delegates to it. Research escalation uses `AnswerAnalyzer.assess()` to gate fast→deep upgrades, with a global `--max-research` cap.

**Tech Stack:** Python 3.11+, `unittest.mock`, existing `lib.client`, `lib.answer_analyzer.AnswerAnalyzer`, `lib.notebook_router.route_notebooks`, `lib.registry`.

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `scripts/lib/plan_evaluator.py` | All four phases + dataclasses |
| Modify | `scripts/nlm.py:410-475` | Thin dispatcher, add `--max-research` |
| Modify | `skills/nlm-plan/SKILL.md` | Updated params + output format |
| Create | `tests/test_plan_evaluator.py` | Unit tests (no auth required) |

---

## Task 1: Dataclasses, SCORE_RE, and PlanEvaluator.__init__

**Files:**
- Create: `scripts/lib/plan_evaluator.py`
- Create: `tests/test_plan_evaluator.py`

- [ ] **Step 1: Write failing tests for dataclass defaults**

Create `tests/test_plan_evaluator.py`:

```python
import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib.plan_evaluator import CriterionEvidence, CriterionScore, PlanEvaluator, _SCORE_RE


def _make_evaluator(local_id="nb-local", global_ids=None, max_research=3):
    """Bypass __init__ to create a pre-wired PlanEvaluator."""
    ev = PlanEvaluator.__new__(PlanEvaluator)
    ev.max_research = max_research
    ev._research_used = 0
    ev._local_nb_id = local_id
    ev._global_nb_ids = global_ids or []
    ev._cache_by_id = {}
    return ev


def test_criterion_evidence_defaults():
    ev = CriterionEvidence(
        option="A", criterion="perf", answer="good", confidence="high", source="local"
    )
    assert ev.research_used is False


def test_criterion_score_defaults():
    s = CriterionScore(option="A", criterion="perf", score=4, reasoning="fast")
    assert s.evidence_gap is False
    assert s.parse_warning is False


def test_score_re_matches_valid():
    import re
    m = _SCORE_RE.search("SCORE: 4\nREASONING: good")
    assert m and m.group(1) == "4"


def test_score_re_no_match_on_missing():
    assert _SCORE_RE.search("It looks pretty good") is None
```

- [ ] **Step 2: Run tests — expect ImportError**

```bash
cd "/Users/marine/Code/NotebookLM SKILL/marine-notebooklm-skill"
.venv/bin/python -m pytest tests/test_plan_evaluator.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError: No module named 'lib.plan_evaluator'`

- [ ] **Step 3: Create `scripts/lib/plan_evaluator.py` with dataclasses and `__init__`**

```python
"""Four-phase comparison evaluator for nlm plan."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from lib import client
from lib.answer_analyzer import AnswerAnalyzer
from lib.notebook_router import route_notebooks
from lib.registry import (
    _resolve_global_ids,
    _resolve_local_id,
    load_notebooks_cache,
    load_project_config,
)

_analyzer = AnswerAnalyzer()
_SCORE_RE = re.compile(r"SCORE:\s*([1-5])", re.IGNORECASE)


@dataclass
class CriterionEvidence:
    option: str
    criterion: str
    answer: str
    confidence: str  # "high" | "medium" | "low" | "not_found"
    source: str      # "local" | "global"
    research_used: bool = False


@dataclass
class CriterionScore:
    option: str
    criterion: str
    score: Optional[int]  # 1-5; None if parse failed or evidence_gap
    reasoning: str
    evidence_gap: bool = False
    parse_warning: bool = False


class PlanEvaluator:
    def __init__(self, project_path: Path, max_research: int = 3):
        self.max_research = max_research
        self._research_used = 0

        cfg = load_project_config(project_path)
        self._local_nb_id: Optional[str] = _resolve_local_id(cfg)
        self._global_nb_ids: list[str] = _resolve_global_ids(cfg)

        cache = load_notebooks_cache(project_path)
        self._cache_by_id: dict[str, dict] = {}
        if cache:
            for nb in cache.get("notebooks", []):
                self._cache_by_id[nb["id"]] = nb
```

- [ ] **Step 4: Run tests — expect 4 passing**

```bash
.venv/bin/python -m pytest tests/test_plan_evaluator.py -v 2>&1 | tail -15
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/plan_evaluator.py tests/test_plan_evaluator.py
git commit -m "feat(plan): add plan_evaluator dataclasses and skeleton"
```

---

## Task 2: _pick_notebook and _ask

**Files:**
- Modify: `scripts/lib/plan_evaluator.py`
- Modify: `tests/test_plan_evaluator.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_plan_evaluator.py`:

```python
# ── _pick_notebook ─────────────────────────────────────────────────────────────

def test_pick_notebook_prefers_local():
    ev = _make_evaluator(local_id="local-nb", global_ids=["global-nb"])
    assert ev._pick_notebook("any question") == "local-nb"


def test_pick_notebook_falls_back_to_global():
    ev = _make_evaluator(local_id=None, global_ids=["global-nb"])
    assert ev._pick_notebook("any question") == "global-nb"


def test_pick_notebook_raises_when_none():
    ev = _make_evaluator(local_id=None, global_ids=[])
    with pytest.raises(ValueError, match="No notebooks configured"):
        ev._pick_notebook("any question")
```

- [ ] **Step 2: Run tests — expect 3 failing**

```bash
.venv/bin/python -m pytest tests/test_plan_evaluator.py::test_pick_notebook_prefers_local tests/test_plan_evaluator.py::test_pick_notebook_falls_back_to_global tests/test_plan_evaluator.py::test_pick_notebook_raises_when_none -v
```

Expected: `FAILED` with `AttributeError: 'PlanEvaluator' object has no attribute '_pick_notebook'`

- [ ] **Step 3: Add `_pick_notebook` and `_ask` to `PlanEvaluator` in `plan_evaluator.py`**

Add inside the `PlanEvaluator` class after `__init__`:

```python
    def _pick_notebook(self, question: str) -> str:
        if self._local_nb_id:
            return self._local_nb_id
        if self._global_nb_ids:
            global_pool = [
                self._cache_by_id[uid]
                for uid in self._global_nb_ids
                if uid in self._cache_by_id
            ]
            if global_pool and any(nb.get("summary") for nb in global_pool):
                try:
                    route = route_notebooks(question, global_pool)
                    if route.ranked_ids:
                        return route.ranked_ids[0]
                except Exception:
                    pass
            return self._global_nb_ids[0]
        raise ValueError("No notebooks configured. Run: nlm setup")

    def _ask(self, question: str) -> dict:
        return client.ask(self._pick_notebook(question), question)
```

- [ ] **Step 4: Run tests — expect 7 passing**

```bash
.venv/bin/python -m pytest tests/test_plan_evaluator.py -v 2>&1 | tail -15
```

Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/plan_evaluator.py tests/test_plan_evaluator.py
git commit -m "feat(plan): add _pick_notebook and _ask with scope routing"
```

---

## Task 3: Phase 1 — _phase1_collect_evidence

**Files:**
- Modify: `scripts/lib/plan_evaluator.py`
- Modify: `tests/test_plan_evaluator.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_plan_evaluator.py`:

```python
# ── Phase 1 ────────────────────────────────────────────────────────────────────

def test_phase1_queries_all_pairs():
    ev = _make_evaluator()
    with patch("lib.plan_evaluator.client") as mock_client:
        mock_client.ask.return_value = {
            "answer": "Detailed info with many specifics [Source 1]. "
                      "Further analysis confirms strong performance in benchmarks. "
                      "Additional considerations include cost and community support.",
            "confidence": "high",
        }
        evidences = ev._phase1_collect_evidence(
            "Which DB?", ["Postgres", "SQLite"], ["performance", "cost"]
        )
    assert len(evidences) == 4
    calls = mock_client.ask.call_args_list
    assert calls[0] == call(
        "nb-local",
        "Evidence for option 'Postgres' on criterion 'performance': Which DB?",
    )
    assert calls[1] == call(
        "nb-local",
        "Evidence for option 'Postgres' on criterion 'cost': Which DB?",
    )
    assert calls[2] == call(
        "nb-local",
        "Evidence for option 'SQLite' on criterion 'performance': Which DB?",
    )
    assert calls[3] == call(
        "nb-local",
        "Evidence for option 'SQLite' on criterion 'cost': Which DB?",
    )


def test_phase1_sets_low_confidence_when_answer_short():
    ev = _make_evaluator()
    with patch("lib.plan_evaluator.client") as mock_client:
        mock_client.ask.return_value = {"answer": "No info.", "confidence": "low"}
        evidences = ev._phase1_collect_evidence("Q?", ["A"], ["perf"])
    assert evidences[0].confidence == "low"


def test_phase1_sets_high_confidence_for_cited_long_answer():
    ev = _make_evaluator()
    long_cited = (
        "This option performs extremely well in production benchmarks [Source 1]. "
        "Multiple independent studies confirm its superiority over alternatives. "
        "The architecture enables horizontal scaling and the API is stable."
    )
    with patch("lib.plan_evaluator.client") as mock_client:
        mock_client.ask.return_value = {"answer": long_cited, "confidence": "high"}
        evidences = ev._phase1_collect_evidence("Q?", ["A"], ["perf"])
    assert evidences[0].confidence == "high"


def test_phase1_source_is_local_when_local_exists():
    ev = _make_evaluator(local_id="nb-local")
    with patch("lib.plan_evaluator.client") as mock_client:
        mock_client.ask.return_value = {"answer": "some answer", "confidence": "medium"}
        evidences = ev._phase1_collect_evidence("Q?", ["A"], ["perf"])
    assert evidences[0].source == "local"


def test_phase1_source_is_global_when_no_local():
    ev = _make_evaluator(local_id=None, global_ids=["global-nb"])
    with patch("lib.plan_evaluator.client") as mock_client:
        mock_client.ask.return_value = {"answer": "some answer", "confidence": "medium"}
        evidences = ev._phase1_collect_evidence("Q?", ["A"], ["perf"])
    assert evidences[0].source == "global"
```

- [ ] **Step 2: Run tests — expect 5 failing**

```bash
.venv/bin/python -m pytest tests/test_plan_evaluator.py -k "phase1" -v
```

Expected: `FAILED` with `AttributeError: 'PlanEvaluator' object has no attribute '_phase1_collect_evidence'`

- [ ] **Step 3: Add `_phase1_collect_evidence` to `PlanEvaluator` in `plan_evaluator.py`**

Add inside the `PlanEvaluator` class after `_ask`:

```python
    def _phase1_collect_evidence(
        self, question: str, options: list[str], criteria: list[str]
    ) -> list[CriterionEvidence]:
        source = "local" if self._local_nb_id else "global"
        evidences: list[CriterionEvidence] = []
        for option in options:
            for criterion in criteria:
                q = f"Evidence for option '{option}' on criterion '{criterion}': {question}"
                r = self._ask(q)
                quality = _analyzer.assess(r["answer"])
                evidences.append(CriterionEvidence(
                    option=option,
                    criterion=criterion,
                    answer=r["answer"],
                    confidence=quality.level,
                    source=source,
                ))
        return evidences
```

- [ ] **Step 4: Run all tests — expect 12 passing**

```bash
.venv/bin/python -m pytest tests/test_plan_evaluator.py -v 2>&1 | tail -20
```

Expected: `12 passed`

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/plan_evaluator.py tests/test_plan_evaluator.py
git commit -m "feat(plan): add phase 1 evidence collection"
```

---

## Task 4: Phase 2 — _phase2_escalate_research

**Files:**
- Modify: `scripts/lib/plan_evaluator.py`
- Modify: `tests/test_plan_evaluator.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_plan_evaluator.py`:

```python
# ── Phase 2 ────────────────────────────────────────────────────────────────────

_HIGH_REPORT = (
    "This option delivers exceptional performance [Source 1]. "
    "Benchmarks confirm its advantages over alternatives consistently. "
    "The architecture enables scalability and the community provides strong support. "
    "Documentation is thorough and the learning curve is manageable for most teams."
)

_LOW_REPORT = "No relevant information found."


def test_phase2_skips_research_when_no_gaps():
    ev = _make_evaluator()
    with patch("lib.plan_evaluator.client") as mock_client:
        reports = ev._phase2_escalate_research("Q?", [])
    mock_client.research.assert_not_called()
    assert reports == {}


def test_phase2_fast_research_when_confident():
    ev = _make_evaluator()
    with patch("lib.plan_evaluator.client") as mock_client:
        mock_client.research.return_value = {"report": _HIGH_REPORT, "status": "completed"}
        reports = ev._phase2_escalate_research("Q?", ["A"])
    mock_client.research.assert_called_once_with(
        "nb-local", "Q? — focus on option 'A'", mode="fast"
    )
    assert reports["A"] == _HIGH_REPORT
    assert ev._research_used == 1


def test_phase2_escalates_to_deep_when_fast_low_confidence():
    ev = _make_evaluator()
    with patch("lib.plan_evaluator.client") as mock_client:
        mock_client.research.side_effect = [
            {"report": _LOW_REPORT, "status": "completed"},   # fast → low
            {"report": _HIGH_REPORT, "status": "completed"},  # deep → high
        ]
        reports = ev._phase2_escalate_research("Q?", ["A"])
    assert mock_client.research.call_count == 2
    assert mock_client.research.call_args_list[0] == call(
        "nb-local", "Q? — focus on option 'A'", mode="fast"
    )
    assert mock_client.research.call_args_list[1] == call(
        "nb-local", "Q? — focus on option 'A'", mode="deep"
    )
    assert reports["A"] == _HIGH_REPORT
    assert ev._research_used == 2


def test_phase2_respects_max_research_cap():
    ev = _make_evaluator(max_research=1)
    with patch("lib.plan_evaluator.client") as mock_client:
        mock_client.research.return_value = {"report": _HIGH_REPORT, "status": "completed"}
        reports = ev._phase2_escalate_research("Q?", ["A", "B"])
    assert "A" in reports
    assert "B" not in reports
    assert ev._research_used == 1


def test_phase2_no_deep_when_cap_reached_after_fast():
    ev = _make_evaluator(max_research=1)
    with patch("lib.plan_evaluator.client") as mock_client:
        # fast returns low confidence, but cap is 1 — no deep allowed
        mock_client.research.return_value = {"report": _LOW_REPORT, "status": "completed"}
        reports = ev._phase2_escalate_research("Q?", ["A"])
    assert mock_client.research.call_count == 1
    assert reports["A"] == _LOW_REPORT  # best available despite low quality
    assert ev._research_used == 1


def test_phase2_skips_when_no_local_notebook():
    ev = _make_evaluator(local_id=None, global_ids=["global-nb"])
    with patch("lib.plan_evaluator.client") as mock_client:
        reports = ev._phase2_escalate_research("Q?", ["A"])
    mock_client.research.assert_not_called()
    assert reports == {}
```

- [ ] **Step 2: Run tests — expect 6 failing**

```bash
.venv/bin/python -m pytest tests/test_plan_evaluator.py -k "phase2" -v
```

Expected: `FAILED` with `AttributeError: 'PlanEvaluator' object has no attribute '_phase2_escalate_research'`

- [ ] **Step 3: Add `_phase2_escalate_research` to `PlanEvaluator` in `plan_evaluator.py`**

Add inside the `PlanEvaluator` class after `_phase1_collect_evidence`:

```python
    def _phase2_escalate_research(
        self, question: str, options_needing_research: list[str]
    ) -> dict[str, str]:
        """Returns {option: research_report} for enriched options."""
        reports: dict[str, str] = {}
        if not self._local_nb_id:
            return reports  # research API requires a local notebook

        for option in options_needing_research:
            if self._research_used >= self.max_research:
                break
            topic = f"{question} — focus on option '{option}'"

            fast_result = client.research(self._local_nb_id, topic, mode="fast")
            self._research_used += 1
            report = fast_result.get("report", "")
            quality = _analyzer.assess(report)

            if quality.level in ("low", "not_found") and self._research_used < self.max_research:
                deep_result = client.research(self._local_nb_id, topic, mode="deep")
                self._research_used += 1
                report = deep_result.get("report", report)

            reports[option] = report
        return reports
```

- [ ] **Step 4: Run all tests — expect 18 passing**

```bash
.venv/bin/python -m pytest tests/test_plan_evaluator.py -v 2>&1 | tail -25
```

Expected: `18 passed`

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/plan_evaluator.py tests/test_plan_evaluator.py
git commit -m "feat(plan): add phase 2 research escalation (fast→deep, max-research cap)"
```

---

## Task 5: Phase 3 — _phase3_score

**Files:**
- Modify: `scripts/lib/plan_evaluator.py`
- Modify: `tests/test_plan_evaluator.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_plan_evaluator.py`:

```python
# ── Phase 3 ────────────────────────────────────────────────────────────────────

def _ev(option="A", criterion="perf", answer="some detail", confidence="high"):
    return CriterionEvidence(
        option=option, criterion=criterion, answer=answer,
        confidence=confidence, source="local"
    )


def test_phase3_parses_score():
    ev = _make_evaluator()
    with patch("lib.plan_evaluator.client") as mock_client:
        mock_client.ask.return_value = {
            "answer": "SCORE: 4\nREASONING: performs well under load",
            "confidence": "high",
        }
        scores = ev._phase3_score([_ev()], research_map={}, gap_options=set())
    assert scores[0].score == 4
    assert scores[0].reasoning == "performs well under load"
    assert scores[0].parse_warning is False
    assert scores[0].evidence_gap is False


def test_phase3_sets_parse_warning_on_missing_score():
    ev = _make_evaluator()
    with patch("lib.plan_evaluator.client") as mock_client:
        mock_client.ask.return_value = {
            "answer": "I think it is pretty good overall",
            "confidence": "medium",
        }
        scores = ev._phase3_score([_ev()], research_map={}, gap_options=set())
    assert scores[0].score is None
    assert scores[0].parse_warning is True


def test_phase3_skips_gap_options_without_asking():
    ev = _make_evaluator()
    evidences = [_ev(option="A"), _ev(option="B")]
    with patch("lib.plan_evaluator.client") as mock_client:
        mock_client.ask.return_value = {
            "answer": "SCORE: 3\nREASONING: adequate",
            "confidence": "medium",
        }
        scores = ev._phase3_score(evidences, research_map={}, gap_options={"B"})
    mock_client.ask.assert_called_once()
    assert scores[0].option == "A" and scores[0].score == 3
    assert scores[1].option == "B" and scores[1].evidence_gap is True
    assert scores[1].score is None


def test_phase3_embeds_research_report_in_prompt():
    ev = _make_evaluator()
    captured: list[str] = []

    def capture_ask(nb_id, question):
        captured.append(question)
        return {"answer": "SCORE: 5\nREASONING: excellent", "confidence": "high"}

    with patch("lib.plan_evaluator.client") as mock_client:
        mock_client.ask.side_effect = capture_ask
        ev._phase3_score(
            [_ev(option="A")],
            research_map={"A": "Extra research data for option A"},
            gap_options=set(),
        )
    assert "Research report:" in captured[0]
    assert "Extra research data for option A" in captured[0]


def test_phase3_prompt_excludes_research_when_not_enriched():
    ev = _make_evaluator()
    captured: list[str] = []

    def capture_ask(nb_id, question):
        captured.append(question)
        return {"answer": "SCORE: 3\nREASONING: ok", "confidence": "medium"}

    with patch("lib.plan_evaluator.client") as mock_client:
        mock_client.ask.side_effect = capture_ask
        ev._phase3_score([_ev(option="A")], research_map={}, gap_options=set())
    assert "Research report:" not in captured[0]
```

- [ ] **Step 2: Run tests — expect 5 failing**

```bash
.venv/bin/python -m pytest tests/test_plan_evaluator.py -k "phase3" -v
```

Expected: `FAILED` with `AttributeError: 'PlanEvaluator' object has no attribute '_phase3_score'`

- [ ] **Step 3: Add `_phase3_score` to `PlanEvaluator` in `plan_evaluator.py`**

Add inside the `PlanEvaluator` class after `_phase2_escalate_research`:

```python
    def _phase3_score(
        self,
        evidences: list[CriterionEvidence],
        research_map: dict[str, str],
        gap_options: set[str],
    ) -> list[CriterionScore]:
        scores: list[CriterionScore] = []
        for ev in evidences:
            if ev.option in gap_options:
                scores.append(CriterionScore(
                    option=ev.option,
                    criterion=ev.criterion,
                    score=None,
                    reasoning="",
                    evidence_gap=True,
                ))
                continue

            research_section = ""
            if ev.option in research_map:
                research_section = f"\nResearch report:\n{research_map[ev.option]}"

            prompt = (
                f"Evidence gathered about '{ev.option}' on '{ev.criterion}':\n"
                f"---\n{ev.answer}{research_section}\n---\n"
                f"Based on the above evidence and your notebook knowledge, "
                f"score option '{ev.option}' on criterion '{ev.criterion}' from 1 to 5 where:\n"
                f"  1 = poor  2 = below average  3 = average  4 = good  5 = excellent\n"
                f"Output format (exactly):\nSCORE: N\nREASONING: one sentence"
            )
            r = self._ask(prompt)
            m = _SCORE_RE.search(r["answer"])
            if m:
                reasoning = (
                    r["answer"].split("REASONING:", 1)[-1].strip()
                    if "REASONING:" in r["answer"]
                    else r["answer"][:200]
                )
                scores.append(CriterionScore(
                    option=ev.option,
                    criterion=ev.criterion,
                    score=int(m.group(1)),
                    reasoning=reasoning,
                ))
            else:
                scores.append(CriterionScore(
                    option=ev.option,
                    criterion=ev.criterion,
                    score=None,
                    reasoning=r["answer"][:200],
                    parse_warning=True,
                ))
        return scores
```

- [ ] **Step 4: Run all tests — expect 23 passing**

```bash
.venv/bin/python -m pytest tests/test_plan_evaluator.py -v 2>&1 | tail -30
```

Expected: `23 passed`

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/plan_evaluator.py tests/test_plan_evaluator.py
git commit -m "feat(plan): add phase 3 structured 1-5 scoring with evidence injection"
```

---

## Task 6: Phase 4 + evaluate() + propose_criteria()

**Files:**
- Modify: `scripts/lib/plan_evaluator.py`
- Modify: `tests/test_plan_evaluator.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_plan_evaluator.py`:

```python
# ── Phase 4 + evaluate ─────────────────────────────────────────────────────────

def test_phase4_computes_equal_weight_mean():
    ev = _make_evaluator()
    scores = [
        CriterionScore("A", "perf", 5, "fast"),
        CriterionScore("A", "cost", 3, "ok"),
        CriterionScore("B", "perf", 2, "slow"),
        CriterionScore("B", "cost", 4, "cheap"),
    ]
    composite, recommendation = ev._phase4_aggregate(scores, ["A", "B"])
    assert composite["A"] == 4.0
    assert composite["B"] == 3.0
    assert recommendation == "A"


def test_phase4_excludes_null_scores_from_mean():
    ev = _make_evaluator()
    scores = [
        CriterionScore("A", "perf", 5, "fast"),
        CriterionScore("A", "cost", None, "", parse_warning=True),
    ]
    composite, _ = ev._phase4_aggregate(scores, ["A"])
    assert composite["A"] == 5.0


def test_phase4_none_composite_when_all_gaps():
    ev = _make_evaluator()
    scores = [CriterionScore("A", "perf", None, "", evidence_gap=True)]
    composite, recommendation = ev._phase4_aggregate(scores, ["A"])
    assert composite["A"] is None
    assert recommendation == "A"  # fallback to first option


def test_evaluate_full_pipeline():
    ev = _make_evaluator()
    evidences_answers = {
        "Evidence for option 'A' on criterion 'perf': Q?": {
            "answer": "A performs well [Source 1]. Benchmarks show strong results under load.",
            "confidence": "high",
        },
        "Evidence for option 'B' on criterion 'perf': Q?": {
            "answer": "B is slower in benchmarks. No citations available in sources.",
            "confidence": "low",
        },
    }

    def mock_ask(nb_id, question):
        if question in evidences_answers:
            return evidences_answers[question]
        # scoring and rationale calls
        if "SCORE:" in question or "score option" in question.lower():
            return {"answer": "SCORE: 4\nREASONING: good", "confidence": "high"}
        return {"answer": "A is the best choice for Q?", "confidence": "high"}

    with patch("lib.plan_evaluator.client") as mock_client:
        mock_client.ask.side_effect = mock_ask
        mock_client.research.return_value = {
            "report": (
                "Option B has moderate performance [Source 1]. "
                "Community benchmarks show it lags behind Option A in throughput. "
                "However it excels in simplicity and lower operational overhead."
            ),
            "status": "completed",
        }
        result = ev.evaluate("Q?", ["A", "B"], ["perf"])

    assert result["recommendation"] in ("A", "B")
    assert "composite_scores" in result
    assert "matrix" in result
    assert "rationale" in result
    assert "research_used" in result
    assert result["max_research"] == 3
    assert isinstance(result["evidence_gaps"], list)


def test_evaluate_lists_unresolved_gaps():
    ev = _make_evaluator(max_research=0)  # no research allowed

    def mock_ask(nb_id, question):
        if "Evidence for" in question:
            return {"answer": "No info.", "confidence": "low"}
        return {"answer": "SCORE: 3\nREASONING: ok", "confidence": "medium"}

    with patch("lib.plan_evaluator.client") as mock_client:
        mock_client.ask.side_effect = mock_ask
        result = ev.evaluate("Q?", ["A"], ["perf"])

    assert "A / perf" in result["evidence_gaps"]
    assert result["research_used"] == 0
```

- [ ] **Step 2: Run tests — expect 5 failing**

```bash
.venv/bin/python -m pytest tests/test_plan_evaluator.py -k "phase4 or evaluate" -v
```

Expected: `FAILED` with `AttributeError`

- [ ] **Step 3: Add `_phase4_aggregate`, `propose_criteria`, and `evaluate` to `PlanEvaluator` in `plan_evaluator.py`**

Add inside the `PlanEvaluator` class after `_phase3_score`:

```python
    def _phase4_aggregate(
        self, scores: list[CriterionScore], options: list[str]
    ) -> tuple[dict[str, float | None], str]:
        composite: dict[str, float | None] = {}
        for option in options:
            valid = [s.score for s in scores if s.option == option and s.score is not None]
            composite[option] = round(sum(valid) / len(valid), 1) if valid else None
        scored = {opt: v for opt, v in composite.items() if v is not None}
        recommendation = max(scored, key=scored.__getitem__) if scored else options[0]
        return composite, recommendation

    def propose_criteria(self, question: str) -> list[str]:
        """Ask NotebookLM to suggest 3-4 evaluation criteria for the question."""
        r = self._ask(
            f"What are 3-4 key evaluation criteria for choosing between options for: {question}"
        )
        lines = [
            line.strip().lstrip("-•*0123456789. ")
            for line in r["answer"].split("\n")
            if line.strip()
        ]
        criteria = [line for line in lines if 3 < len(line) < 80][:4]
        return criteria or ["performance", "maintainability", "cost", "complexity"]

    def evaluate(self, question: str, options: list[str], criteria: list[str]) -> dict:
        # Phase 1: collect evidence per option×criterion
        evidences = self._phase1_collect_evidence(question, options, criteria)

        # Options needing research (any criterion with low/not_found confidence)
        low_conf_options = sorted({
            ev.option for ev in evidences
            if ev.confidence in ("low", "not_found")
        })

        # Phase 2: research escalation
        research_map = self._phase2_escalate_research(question, low_conf_options)

        # Options still without resolved evidence (budget exhausted)
        gap_options: set[str] = set(low_conf_options) - set(research_map.keys())

        # Phase 3: structured scoring
        scores = self._phase3_score(evidences, research_map, gap_options)

        # Phase 4: aggregation
        composite, recommendation = self._phase4_aggregate(scores, options)

        # Rationale for winning option
        if recommendation not in gap_options:
            r = self._ask(
                f"In one sentence, why is '{recommendation}' the best choice for: {question}"
            )
            rationale = r["answer"]
        else:
            rationale = (
                f"'{recommendation}' selected by default; "
                f"evidence was insufficient for full comparison."
            )

        # Build matrix
        matrix: dict[str, dict] = {opt: {} for opt in options}
        for s in scores:
            entry: dict = {"score": s.score, "reasoning": s.reasoning}
            if s.evidence_gap:
                entry["evidence_gap"] = True
            if s.parse_warning:
                entry["parse_warning"] = True
            matrix[s.option][s.criterion] = entry

        evidence_gaps = [
            f"{s.option} / {s.criterion}" for s in scores if s.evidence_gap
        ]

        return {
            "recommendation": recommendation,
            "composite_scores": composite,
            "matrix": matrix,
            "rationale": rationale,
            "research_used": self._research_used,
            "max_research": self.max_research,
            "evidence_gaps": evidence_gaps,
        }
```

- [ ] **Step 4: Run all tests — expect 28 passing**

```bash
.venv/bin/python -m pytest tests/test_plan_evaluator.py -v 2>&1 | tail -35
```

Expected: `28 passed`

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/plan_evaluator.py tests/test_plan_evaluator.py
git commit -m "feat(plan): add phase 4 aggregation + evaluate() + propose_criteria()"
```

---

## Task 7: Rewrite cmd_plan in nlm.py

**Files:**
- Modify: `scripts/nlm.py:410-475`

- [ ] **Step 1: Replace `cmd_plan` in `scripts/nlm.py`**

Replace the entire `cmd_plan` function (lines 410–475) with:

```python
def cmd_plan(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="nlm plan")
    parser.add_argument("--question", required=True)
    parser.add_argument("--options", required=True, help="Comma-separated options e.g. 'A,B,C'")
    parser.add_argument("--criteria", default="", help="Comma-separated evaluation criteria")
    parser.add_argument("--max-research", type=int, default=3, dest="max_research")
    parser.add_argument("--project-path", default=".")
    parsed = parser.parse_args(args)

    assert_authenticated()
    project_path = Path(parsed.project_path).expanduser().resolve()

    options = [o.strip() for o in parsed.options.split(",") if o.strip()]
    criteria = [c.strip() for c in parsed.criteria.split(",") if c.strip()] if parsed.criteria else []

    from lib.plan_evaluator import PlanEvaluator
    evaluator = PlanEvaluator(project_path, max_research=parsed.max_research)

    if not evaluator._local_nb_id and not evaluator._global_nb_ids:
        print(json.dumps({"error": "No notebooks configured. Run: nlm setup"}))
        sys.exit(1)

    if not criteria:
        criteria = evaluator.propose_criteria(parsed.question)

    result = evaluator.evaluate(parsed.question, options, criteria)
    print(json.dumps(result, indent=2, ensure_ascii=False))
```

- [ ] **Step 2: Remove the now-unused `find_notebook_ids` import in `nlm.py`**

Check if `find_notebook_ids` is still used elsewhere in the file:

```bash
grep -n "find_notebook_ids" "/Users/marine/Code/NotebookLM SKILL/marine-notebooklm-skill/scripts/nlm.py"
```

If the only remaining reference is the import line, remove it from the import block at the top of the file. The import block currently reads:

```python
from lib.registry import (
    find_notebook_ids, load_global_config, load_project_config,
    save_global_config, save_project_config,
    load_notebooks_cache, save_notebooks_cache,
    _resolve_local_id, _resolve_global_ids,
)
```

Remove `find_notebook_ids,` from this import if no other usage exists.

- [ ] **Step 3: Verify the existing unit tests still pass**

```bash
.venv/bin/python -m pytest tests/test_plan_evaluator.py tests/test_registry.py -v 2>&1 | tail -20
```

Expected: all tests pass

- [ ] **Step 4: Smoke-test arg parsing manually**

```bash
cd "/Users/marine/Code/NotebookLM SKILL/marine-notebooklm-skill"
.venv/bin/python scripts/nlm.py plan --help
```

Expected output includes: `--max-research`, `--question`, `--options`, `--criteria`, `--project-path`

- [ ] **Step 5: Commit**

```bash
git add scripts/nlm.py
git commit -m "feat(plan): rewrite cmd_plan as thin dispatcher using PlanEvaluator"
```

---

## Task 8: Update SKILL.md and deploy

**Files:**
- Modify: `skills/nlm-plan/SKILL.md`

- [ ] **Step 1: Replace `skills/nlm-plan/SKILL.md` with updated content**

```markdown
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
INVOKE="bash $HOME/.claude/skills/nlm/scripts/invoke.sh"
$INVOKE plan --question "<decision>" --options "A,B" --criteria "performance,maintainability"
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
```

- [ ] **Step 2: Deploy to `~/.claude/skills/`**

```bash
cp "/Users/marine/Code/NotebookLM SKILL/marine-notebooklm-skill/skills/nlm-plan/SKILL.md" \
   ~/.claude/skills/nlm-plan/SKILL.md

rsync -av --delete \
  "/Users/marine/Code/NotebookLM SKILL/marine-notebooklm-skill/scripts/" \
  ~/.claude/skills/nlm/scripts/
```

- [ ] **Step 3: Verify deployment**

```bash
head -5 ~/.claude/skills/nlm-plan/SKILL.md
```

Expected first lines include `name: nlm-plan` and description mentioning `1–5 numeric score`.

- [ ] **Step 4: Commit**

```bash
git add "skills/nlm-plan/SKILL.md"
git commit -m "docs(nlm-plan): update SKILL.md for 1-5 scoring, composite scores, max-research"
```
