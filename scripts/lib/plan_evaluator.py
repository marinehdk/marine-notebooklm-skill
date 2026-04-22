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
