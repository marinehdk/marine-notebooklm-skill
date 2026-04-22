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


# ── Phase 1 ────────────────────────────────────────────────────────────────────

def test_phase1_makes_single_batched_call():
    """Verify Phase 1 now makes 1 API call instead of 4 (2 options × 2 criteria)."""
    ev = _make_evaluator()
    with patch("lib.plan_evaluator.client") as mock_client:
        mock_client.ask.return_value = {
            "answer": (
                "Postgres|performance: Excellent performance [Source 1]. "
                "Benchmarks confirm consistent high throughput.\n"
                "Postgres|cost: Moderate cost with reasonable operational overhead.\n"
                "SQLite|performance: Good performance for small datasets [Source 1].\n"
                "SQLite|cost: Very low cost, minimal resource requirements."
            ),
            "confidence": "high",
        }
        evidences = ev._phase1_collect_evidence(
            "Which DB?", ["Postgres", "SQLite"], ["performance", "cost"]
        )

    # Verify only 1 call was made
    assert len(mock_client.ask.call_args_list) == 1
    # Verify 4 evidences returned (2 options × 2 criteria)
    assert len(evidences) == 4
    # Verify evidences contain expected option/criterion combinations
    ev_map = {(e.option, e.criterion): e for e in evidences}
    assert ("Postgres", "performance") in ev_map
    assert ("Postgres", "cost") in ev_map
    assert ("SQLite", "performance") in ev_map
    assert ("SQLite", "cost") in ev_map
    assert ev_map[("Postgres", "performance")].answer == "Excellent performance [Source 1]. Benchmarks confirm consistent high throughput."
    assert ev_map[("Postgres", "cost")].answer == "Moderate cost with reasonable operational overhead."


def test_phase1_sets_low_confidence_when_answer_short():
    ev = _make_evaluator()
    with patch("lib.plan_evaluator.client") as mock_client:
        mock_client.ask.return_value = {"answer": "A|perf: No info.", "confidence": "low"}
        evidences = ev._phase1_collect_evidence("Q?", ["A"], ["perf"])
    assert len(evidences) == 1
    assert evidences[0].confidence == "low"


def test_phase1_sets_high_confidence_for_cited_long_answer():
    ev = _make_evaluator()
    long_cited = (
        "A|perf: This option performs extremely well in production benchmarks [Source 1]. "
        "Multiple independent studies confirm its superiority over alternatives. "
        "The architecture enables horizontal scaling and the API is stable. "
        "The performance metrics demonstrate consistent improvements across all measured dimensions. "
        "Community adoption and support are excellent with strong documentation and tutorials readily available."
    )
    with patch("lib.plan_evaluator.client") as mock_client:
        mock_client.ask.return_value = {"answer": long_cited, "confidence": "high"}
        evidences = ev._phase1_collect_evidence("Q?", ["A"], ["perf"])
    assert len(evidences) == 1
    assert evidences[0].confidence == "high"


def test_phase1_source_is_local_when_local_exists():
    ev = _make_evaluator(local_id="nb-local")
    with patch("lib.plan_evaluator.client") as mock_client:
        mock_client.ask.return_value = {"answer": "A|perf: some answer", "confidence": "medium"}
        evidences = ev._phase1_collect_evidence("Q?", ["A"], ["perf"])
    assert evidences[0].source == "local"


def test_phase1_source_is_global_when_no_local():
    ev = _make_evaluator(local_id=None, global_ids=["global-nb"])
    with patch("lib.plan_evaluator.client") as mock_client:
        mock_client.ask.return_value = {"answer": "A|perf: some answer", "confidence": "medium"}
        evidences = ev._phase1_collect_evidence("Q?", ["A"], ["perf"])
    assert evidences[0].source == "global"


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


def test_phase2_skips_research_when_all_high_confidence():
    ev = _make_evaluator()
    evidences = [
        _ev(option="A", confidence="high"),
        _ev(option="B", confidence="high"),
    ]
    with patch("lib.plan_evaluator.client") as mock_client:
        reports = ev._phase2_escalate_research("Q?", evidences)
    mock_client.research.assert_not_called()
    assert reports == {}


def test_phase2_fast_research_when_low_confidence():
    ev = _make_evaluator()
    evidences = [_ev(option="A", confidence="low")]
    with patch("lib.plan_evaluator.client") as mock_client:
        mock_client.research.return_value = {"report": _HIGH_REPORT, "status": "completed"}
        reports = ev._phase2_escalate_research("Q?", evidences)
    mock_client.research.assert_called_once_with(
        "nb-local", "Q? — focus on option 'A'", mode="fast"
    )
    assert reports["A"] == _HIGH_REPORT
    assert ev._research_used == 1


def test_phase2_no_deep_escalation_only_fast():
    ev = _make_evaluator()
    evidences = [_ev(option="A", confidence="not_found")]
    with patch("lib.plan_evaluator.client") as mock_client:
        mock_client.research.return_value = {"report": _LOW_REPORT, "status": "completed"}
        reports = ev._phase2_escalate_research("Q?", evidences)
    # Should only call fast mode, never deep mode
    assert mock_client.research.call_count == 1
    assert mock_client.research.call_args_list[0] == call(
        "nb-local", "Q? — focus on option 'A'", mode="fast"
    )
    assert reports["A"] == _LOW_REPORT
    assert ev._research_used == 1


def test_phase2_respects_max_research_cap():
    ev = _make_evaluator(max_research=1)
    evidences = [
        _ev(option="A", confidence="low"),
        _ev(option="A", confidence="not_found"),
        _ev(option="B", confidence="low"),
    ]
    with patch("lib.plan_evaluator.client") as mock_client:
        mock_client.research.return_value = {"report": _HIGH_REPORT, "status": "completed"}
        reports = ev._phase2_escalate_research("Q?", evidences)
    # Only top 1 option (A with 2 low/not_found) gets researched
    assert "A" in reports
    assert "B" not in reports
    assert ev._research_used == 1




def test_phase2_skips_when_no_local_notebook():
    ev = _make_evaluator(local_id=None, global_ids=["global-nb"])
    evidences = [_ev(option="A", confidence="low")]
    with patch("lib.plan_evaluator.client") as mock_client:
        reports = ev._phase2_escalate_research("Q?", evidences)
    mock_client.research.assert_not_called()
    assert reports == {}


def test_phase2_selective_top_n_by_neediness():
    """Verify only top 2-3 options by neediness (count of low/not_found) are researched."""
    ev = _make_evaluator(max_research=5)
    # A: 2 low/not_found, B: 1 low, C: 1 low
    evidences = [
        _ev(option="A", criterion="perf", confidence="low"),
        _ev(option="A", criterion="cost", confidence="not_found"),
        _ev(option="B", criterion="perf", confidence="low"),
        _ev(option="C", criterion="cost", confidence="low"),
    ]
    with patch("lib.plan_evaluator.client") as mock_client:
        mock_client.research.return_value = {"report": _HIGH_REPORT, "status": "completed"}
        reports = ev._phase2_escalate_research("Q?", evidences)

    # Should research A (neediness=2) and B or C (neediness=1 each), max 2-3
    # In this case: A (score 2), B (score 1), C (score 1) — top 3 would select A, B, C
    # But max is limited to 3 options, so all three get researched if budget allows
    assert "A" in reports
    assert mock_client.research.call_count == 3  # A, B, C
    assert ev._research_used == 3


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
            "answer": "A|perf,4,performs well under load",
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
            "answer": "A|perf,invalid,I think it is pretty good overall",
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
            "answer": "A|perf,3,adequate",
            "confidence": "medium",
        }
        scores = ev._phase3_score(evidences, research_map={}, gap_options={"B"})
    mock_client.ask.assert_called_once()
    # Gap options are added first, so B comes before A in the scores list
    assert len(scores) == 2
    assert scores[0].option == "B" and scores[0].evidence_gap is True
    assert scores[1].option == "A" and scores[1].score == 3


def test_phase3_embeds_research_report_in_prompt():
    ev = _make_evaluator()
    captured: list[str] = []

    def capture_ask(nb_id, question):
        captured.append(question)
        return {"answer": "A|perf,5,excellent", "confidence": "high"}

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
        return {"answer": "A|perf,3,ok", "confidence": "medium"}

    with patch("lib.plan_evaluator.client") as mock_client:
        mock_client.ask.side_effect = capture_ask
        ev._phase3_score([_ev(option="A")], research_map={}, gap_options=set())
    assert "Research report:" not in captured[0]


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
        return {"answer": "A|perf,3,ok", "confidence": "medium"}

    with patch("lib.plan_evaluator.client") as mock_client:
        mock_client.ask.side_effect = mock_ask
        result = ev.evaluate("Q?", ["A"], ["perf"])

    assert "A / perf" in result["evidence_gaps"]
    assert result["research_used"] == 0


# ── propose_criteria markdown stripping ────────────────────────────────────────

def test_propose_criteria_strips_trailing_asterisks():
    """LLM may return **bold** criteria; trailing ** must be stripped."""
    ev = _make_evaluator()
    with patch("lib.plan_evaluator.client") as mock_client:
        mock_client.ask.return_value = {
            "answer": (
                "**执行确定性 (Determinism)**\n"
                "**自动化程度 (Automation)**\n"
                "**Token 消耗 (Token Cost)**\n"
            ),
            "confidence": "high",
        }
        criteria = ev.propose_criteria("Which approach?")

    assert all("**" not in c for c in criteria), f"Trailing ** found in: {criteria}"
    assert all("*" not in c for c in criteria), f"Stray * found in: {criteria}"
    assert any("Determinism" in c for c in criteria)


def test_propose_criteria_strips_leading_asterisks():
    """Criteria starting with * or ** must have those stripped."""
    ev = _make_evaluator()
    with patch("lib.plan_evaluator.client") as mock_client:
        mock_client.ask.return_value = {
            "answer": "* performance\n** cost\n*- complexity\n",
            "confidence": "high",
        }
        criteria = ev.propose_criteria("Q?")

    assert all(not c.startswith("*") for c in criteria), f"Leading * found in: {criteria}"


def test_phase3_normalizes_criterion_with_trailing_asterisks():
    """Scoring must succeed even if criterion keys contain trailing **."""
    ev = _make_evaluator()
    evidence = CriterionEvidence(
        option="Hooks",
        criterion="执行确定性 (Determinism)**",  # trailing ** leaked in
        answer="Hooks are deterministic.",
        confidence="high",
        source="local",
    )
    # LLM responds with criterion WITHOUT trailing **
    with patch("lib.plan_evaluator.client") as mock_client:
        mock_client.ask.return_value = {
            "answer": "Hooks|执行确定性 (Determinism),5,always runs",
            "confidence": "high",
        }
        scores = ev._phase3_score([evidence], research_map={}, gap_options=set())

    assert scores[0].score == 5, f"Expected score 5, got {scores[0].score} (parse_warning={scores[0].parse_warning})"
    assert scores[0].parse_warning is False
