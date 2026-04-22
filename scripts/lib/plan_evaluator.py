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
