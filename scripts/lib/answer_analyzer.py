"""Analyze NotebookLM answer quality and confidence level."""

from __future__ import annotations
import re
from dataclasses import dataclass


UNCERTAINTY_SIGNALS = [
    "i don't have information",
    "the sources don't mention",
    "i couldn't find",
    "not covered in",
    "based on the available sources, i cannot",
    "i don't have enough information",
    "the provided sources do not",
    "没有相关信息",
    "文档中未提及",
    "无法找到",
    "来源中没有",
]

CITATION_PATTERN = re.compile(r"\[Source \d+\]|\[来源 \d+\]|\[\d+\]")


@dataclass
class AnswerQuality:
    """Assessment of a NotebookLM answer."""
    level: str  # "high" | "medium" | "low" | "not_found"
    confidence: float  # 0.0-1.0
    has_citations: bool
    citation_count: int
    suggestion: str  # "use_as_is" | "ask_followup" | "escalate_to_web" | "cross_notebook"


class AnswerAnalyzer:
    """Analyze NotebookLM response quality."""

    def assess(self, answer: str, references: list = None) -> AnswerQuality:
        """Assess answer quality based on content analysis."""
        if not answer or not answer.strip():
            return AnswerQuality(
                level="not_found",
                confidence=0.0,
                has_citations=False,
                citation_count=0,
                suggestion="escalate_to_web",
            )

        answer_lower = answer.lower()

        # Check for uncertainty signals
        is_uncertain = any(signal in answer_lower for signal in UNCERTAINTY_SIGNALS)
        if is_uncertain:
            return AnswerQuality(
                level="not_found",
                confidence=0.1,
                has_citations=False,
                citation_count=0,
                suggestion="escalate_to_web",
            )

        # Count citations
        citations = CITATION_PATTERN.findall(answer)
        citation_count = len(citations)
        ref_count = len(references) if references else 0
        has_citations = citation_count > 0 or ref_count > 0

        # Length and detail assessment
        word_count = len(answer.split())

        if has_citations and word_count > 50:
            return AnswerQuality(
                level="high",
                confidence=0.9,
                has_citations=True,
                citation_count=max(citation_count, ref_count),
                suggestion="use_as_is",
            )
        elif has_citations or word_count > 30:
            return AnswerQuality(
                level="medium",
                confidence=0.6,
                has_citations=has_citations,
                citation_count=max(citation_count, ref_count),
                suggestion="ask_followup",
            )
        else:
            return AnswerQuality(
                level="low",
                confidence=0.3,
                has_citations=has_citations,
                citation_count=max(citation_count, ref_count),
                suggestion="escalate_to_web",
            )

    def needs_escalation(self, quality: AnswerQuality) -> bool:
        """Whether the answer quality warrants escalation to web research."""
        return quality.level in ("low", "not_found")
