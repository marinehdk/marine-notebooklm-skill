"""Four-phase comparison evaluator for nlm plan."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from lib import client
from lib.answer_analyzer import AnswerAnalyzer
from lib.notebook_router import route_notebooks
from lib.progress import step, done, info
from lib.registry import (
    _resolve_global_ids,
    _resolve_local_id,
    load_notebooks_cache,
    load_project_config,
)

_analyzer = AnswerAnalyzer()
_SCORE_RE = re.compile(r"SCORE:\s*([1-5])", re.IGNORECASE)


def _norm_criterion(s: str) -> str:
    """Strip markdown bold markers and whitespace from a criterion name."""
    return s.strip("* ").strip()


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

    def _phase1_collect_evidence(
        self, question: str, options: list[str], criteria: list[str]
    ) -> list[CriterionEvidence]:
        source = "local" if self._local_nb_id else "global"

        # Build single structured prompt for all option×criterion combinations
        batch_prompt = self._build_batch_evidence_prompt(question, options, criteria)

        # Make ONE API call instead of len(options) * len(criteria) calls
        response = self._ask(batch_prompt)

        # Parse response to extract evidence for each option×criterion pair
        evidences = self._parse_batch_evidence(response["answer"], options, criteria, source)

        return evidences

    def _build_batch_evidence_prompt(
        self, question: str, options: list[str], criteria: list[str]
    ) -> str:
        """Build a single prompt requesting evidence for all option×criterion combinations."""
        prompt = f"Question: {question}\n\n"
        prompt += "Provide evidence for each option-criterion combination below.\n"
        prompt += "Output each piece of evidence with the format:\n"
        prompt += "[OPTION]|[CRITERION]: [evidence text]\n\n"

        prompt += "Evidence needed:\n"
        for option in options:
            for criterion in criteria:
                prompt += f"  - {option} / {criterion}\n"

        prompt += "\nProvide detailed evidence for each combination, citing your sources where applicable."
        return prompt

    def _parse_batch_evidence(
        self, response_text: str, options: list[str], criteria: list[str], source: str
    ) -> list[CriterionEvidence]:
        """Parse batch response to extract evidence for each option×criterion pair."""
        evidences: list[CriterionEvidence] = []

        # Build a map of option|criterion -> evidence text from the response
        evidence_map: dict[tuple[str, str], str] = {}

        # Look for lines with pattern: [OPTION]|[CRITERION]: [evidence]
        lines = response_text.split("\n")
        for line in lines:
            if "|" in line and ":" in line:
                try:
                    # Extract key and evidence from "[OPTION]|[CRITERION]: evidence..."
                    key_part, evidence = line.split(":", 1)
                    key_part = key_part.strip()

                    if "|" in key_part:
                        option, criterion = key_part.split("|", 1)
                        option = option.strip()
                        criterion = criterion.strip()
                        evidence_text = evidence.strip()

                        # Only include if option and criterion match expected values
                        if option in options and criterion in criteria:
                            evidence_map[(option, criterion)] = evidence_text
                except (ValueError, IndexError):
                    # Skip malformed lines
                    pass

        # Build CriterionEvidence for each option×criterion pair
        for option in options:
            for criterion in criteria:
                key = (option, criterion)
                if key in evidence_map:
                    answer = evidence_map[key]
                else:
                    # Fallback: try to find relevant section in response
                    answer = self._extract_fallback_evidence(
                        response_text, option, criterion
                    )

                quality = _analyzer.assess(answer)
                evidences.append(CriterionEvidence(
                    option=option,
                    criterion=criterion,
                    answer=answer,
                    confidence=quality.level,
                    source=source,
                ))

        return evidences

    def _extract_fallback_evidence(self, text: str, option: str, criterion: str) -> str:
        """Fallback extraction when batch parsing doesn't find exact key-value pair."""
        lines = text.split("\n")

        # Look for a line mentioning both option and criterion
        for i, line in enumerate(lines):
            if option.lower() in line.lower() and criterion.lower() in line.lower():
                # Collect next several lines as evidence
                evidence_lines = [line]
                for j in range(i + 1, min(i + 4, len(lines))):
                    if lines[j].strip():
                        evidence_lines.append(lines[j])
                    else:
                        break
                return "\n".join(evidence_lines).strip()

        # Last resort: return empty string (will be scored as "not_found")
        return ""

    def _phase2_escalate_research(
        self, question: str, evidences: list[CriterionEvidence]
    ) -> dict[str, str]:
        """Returns {option: research_report} for enriched options.

        Selects only the top 2-3 most problematic options (by count of low/not_found
        confidences) and uses fast-mode research only to reduce budget.
        """
        reports: dict[str, str] = {}
        if not self._local_nb_id:
            return reports  # research API requires a local notebook

        # Score options by "neediness": count of low/not_found confidences per option
        option_scores: dict[str, int] = {}
        for ev in evidences:
            if ev.confidence in ("low", "not_found"):
                option_scores[ev.option] = option_scores.get(ev.option, 0) + 1

        if not option_scores:
            return reports  # no problematic options

        # Select top 2-3 options by neediness (most low/not_found confidences)
        top_options = sorted(
            option_scores.items(), key=lambda x: x[1], reverse=True
        )[:3]  # max 3 options
        options_to_research = [opt for opt, count in top_options]

        for option in options_to_research:
            if self._research_used >= self.max_research:
                break
            topic = f"{question} — focus on option '{option}'"

            # Use fast mode only (no deep escalation)
            fast_result = client.research(self._local_nb_id, topic, mode="fast")
            self._research_used += 1
            report = fast_result.get("report", "")

            reports[option] = report
        return reports

    def _phase3_score(
        self,
        evidences: list[CriterionEvidence],
        research_map: dict[str, str],
        gap_options: set[str],
    ) -> list[CriterionScore]:
        scores: list[CriterionScore] = []

        # Separate gap options from scored ones
        to_score = [ev for ev in evidences if ev.option not in gap_options]

        # Handle gap options first
        for ev in evidences:
            if ev.option in gap_options:
                scores.append(CriterionScore(
                    option=ev.option,
                    criterion=ev.criterion,
                    score=None,
                    reasoning="",
                    evidence_gap=True,
                ))

        # If nothing to score, return early
        if not to_score:
            return scores

        # Build single batch prompt for all option×criterion pairs
        evidence_lines: list[str] = []
        for ev in to_score:
            research_section = ""
            if ev.option in research_map:
                research_section = f"\nResearch report:\n{research_map[ev.option]}"

            evidence_lines.append(
                f"[{ev.option}|{_norm_criterion(ev.criterion)}]\n{ev.answer}{research_section}"
            )

        batch_prompt = (
            "Score each evidence statement below from 1 to 5:\n"
            "  1 = poor  2 = below average  3 = average  4 = good  5 = excellent\n\n"
            + "\n\n---\n\n".join(evidence_lines) + "\n\n"
            "Output one line per evidence, format: OPTION|CRITERION,SCORE,REASONING\n"
            "Example: A|performance,4,performs well under load\n"
            "Example: B|cost,2,expensive solution"
        )

        # Single API call for all scores
        r = self._ask(batch_prompt)
        response_text = r["answer"]

        # Parse response: build a dict keyed by (option, criterion)
        parsed_scores: dict[tuple[str, str], tuple[int | None, str, bool]] = {}
        for line in response_text.split("\n"):
            line = line.strip()
            if not line:
                continue

            # Try to parse: OPTION|CRITERION,SCORE,REASONING
            parts = line.split(",", 2)
            if len(parts) >= 2:
                key_part = parts[0].strip()
                score_part = parts[1].strip()
                reasoning_part = parts[2].strip() if len(parts) > 2 else ""

                # Extract option and criterion from "OPTION|CRITERION"
                if "|" in key_part:
                    opt, crit = key_part.split("|", 1)
                    opt = opt.strip()
                    crit = crit.strip()

                    # Try to parse score (accept both "4" and "SCORE: 4" formats)
                    score = None
                    parse_warning = True

                    # First try the "SCORE: N" format
                    score_match = _SCORE_RE.search(score_part)
                    if score_match:
                        score = int(score_match.group(1))
                        parse_warning = False
                    else:
                        # Try to parse plain number (1-5)
                        score_part_stripped = score_part.split()[0] if score_part else ""
                        if score_part_stripped.isdigit():
                            num = int(score_part_stripped)
                            if 1 <= num <= 5:
                                score = num
                                parse_warning = False

                    if score is not None:
                        parsed_scores[(opt, crit)] = (score, reasoning_part, parse_warning)
                    else:
                        # Score parsing failed
                        parsed_scores[(opt, crit)] = (None, line[:200], True)

        # Build final scores list in order of evidences
        for ev in to_score:
            key = (ev.option, _norm_criterion(ev.criterion))
            if key in parsed_scores:
                score, reasoning, parse_warning = parsed_scores[key]
                scores.append(CriterionScore(
                    option=ev.option,
                    criterion=ev.criterion,
                    score=score,
                    reasoning=reasoning,
                    parse_warning=parse_warning,
                ))
            else:
                # Not found in parsed response
                scores.append(CriterionScore(
                    option=ev.option,
                    criterion=ev.criterion,
                    score=None,
                    reasoning="",
                    parse_warning=True,
                ))

        return scores

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
            line.strip().lstrip("-•*0123456789. ").rstrip("* ").strip()
            for line in r["answer"].split("\n")
            if line.strip()
        ]
        criteria = [line for line in lines if 3 < len(line) < 80][:4]
        return criteria or ["performance", "maintainability", "cost", "complexity"]

    def evaluate(self, question: str, options: list[str], criteria: list[str]) -> dict:
        total_phases = 4
        n_pairs = len(options) * len(criteria)

        # Phase 1: collect evidence per option×criterion (single batch call)
        step(1, total_phases, f"Collecting evidence for {n_pairs} option×criterion pairs (1 batch call)...")
        evidences = self._phase1_collect_evidence(question, options, criteria)
        low_conf = sum(1 for ev in evidences if ev.confidence in ("low", "not_found"))
        done(1, total_phases, f"Evidence collected — {n_pairs - low_conf}/{n_pairs} high/medium confidence")

        # Phase 2: research escalation (selective, top 2-3 most problematic options)
        needy_options = {ev.option for ev in evidences if ev.confidence in ("low", "not_found")}
        if needy_options:
            step(2, total_phases, f"Researching {len(needy_options)} low-confidence option(s): {', '.join(sorted(needy_options))}...")
        else:
            info(f"[2/{total_phases}] All options have sufficient evidence — skipping research")
        research_map = self._phase2_escalate_research(question, evidences)
        if needy_options:
            done(2, total_phases, f"Research complete ({self._research_used} call(s) used)")

        # Options still without resolved evidence (budget exhausted)
        low_conf_options = {
            ev.option for ev in evidences
            if ev.confidence in ("low", "not_found")
        }
        gap_options: set[str] = low_conf_options - set(research_map.keys())

        # Phase 3: structured scoring (single batch call)
        step(3, total_phases, f"Scoring all {n_pairs} option×criterion pairs (1 batch call)...")
        scores = self._phase3_score(evidences, research_map, gap_options)
        valid_scores = sum(1 for s in scores if s.score is not None)
        done(3, total_phases, f"Scoring complete — {valid_scores}/{n_pairs} scored successfully")

        # Phase 4: aggregation + rationale
        step(4, total_phases, "Aggregating scores and generating recommendation...")
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
        done(4, total_phases, f"Recommendation: {recommendation}")

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
