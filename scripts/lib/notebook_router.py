"""Route questions to the most relevant notebooks via Claude Haiku.

Falls back to title keyword matching if the API call fails.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import anthropic


_STOP_WORDS = frozenset(
    "the a an is in of to and for how what does did does can could would should".split()
)

_ROUTER_MODEL = "claude-haiku-4-5-20251001"


@dataclass
class RouteResult:
    ranked_ids: list[str] = field(default_factory=list)
    fallback_used: bool = False


def route_notebooks(question: str, notebooks: list[dict], scope: str = "auto") -> RouteResult:
    """Return notebooks ranked by relevance to question.

    Args:
        question: The user's question text.
        notebooks: List of notebook dicts with keys: id, title, summary, topics.
        scope: Informational only — caller is responsible for passing the right pool.

    Returns:
        RouteResult with ranked_ids (≤3) and fallback_used flag.
    """
    if not notebooks:
        return RouteResult()

    try:
        ranked = _claude_route(question, notebooks)
        valid_ids = {nb["id"] for nb in notebooks}
        ranked = [uid for uid in ranked if uid in valid_ids][:3]
        return RouteResult(ranked_ids=ranked, fallback_used=False)
    except Exception:
        return RouteResult(ranked_ids=_keyword_rank(question, notebooks), fallback_used=True)


def _claude_route(question: str, notebooks: list[dict]) -> list[str]:
    """Ask Claude Haiku to rank notebooks by relevance. Returns UUID list."""
    lines = []
    for i, nb in enumerate(notebooks, 1):
        summary = (nb.get("summary") or "")[:200]
        topics = " / ".join((nb.get("topics") or [])[:3])
        lines.append(
            f'[{i}] UUID: {nb["id"]} | Title: {nb["title"]}\n'
            f'    Summary: {summary}\n'
            f'    Topics: {topics}'
        )

    prompt = (
        "You are a notebook router. Given a question and a list of notebooks, "
        "return the UUIDs of the most relevant notebooks in order of relevance.\n\n"
        f"Question: {question}\n\n"
        "Notebooks:\n" + "\n\n".join(lines) + "\n\n"
        "Reply with ONLY a JSON array of UUIDs, most relevant first. Include at most 3.\n"
        'Example: ["uuid-1", "uuid-2"]'
    )

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=_ROUTER_MODEL,
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}],
    )
    return json.loads(response.content[0].text.strip())


def _keyword_rank(question: str, notebooks: list[dict]) -> list[str]:
    """Rank notebooks by title keyword overlap with question."""
    tokens = {
        t.lower()
        for t in re.split(r"[\s\W]+", question)
        if t and t.lower() not in _STOP_WORDS
    }
    scores: list[tuple[int, str]] = []
    for nb in notebooks:
        title_lower = nb["title"].lower()
        score = sum(1 for t in tokens if t in title_lower)
        scores.append((score, nb["id"]))
    scores.sort(reverse=True)
    return [uid for _, uid in scores[:3]]
