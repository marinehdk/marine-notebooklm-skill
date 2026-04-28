"""Classify a topic or query into a domain notebook key.

No external LLM calls — pure local keyword matching against config domain definitions.

Returns one of:
  domain_key   — matched domain from config.domain_notebooks
  "local"      — below threshold, route to project local notebook
  "NEW:<name>" — no domain matches; caller should run domain guard before creating
"""
from __future__ import annotations

import re
from pathlib import Path

from .registry import load_project_config

_STOP_WORDS = frozenset(
    "the a an is in of to and for how what does did can could would should "
    "with this that are be was were has have had will from by at on or not "
    "if but when then also which we i you it he she they their our your my "
    "的 了 是 在 和 与 或 对 中 为 以 将 这 该 其 一 个".split()
)

# Confidence thresholds (fraction of topic tokens matched)
_HIGH_THRESHOLD = 0.25   # → route to matched domain
_LOW_THRESHOLD = 0.10    # → route to local (below this → suggest new domain)


def classify_domain(text: str, project_path: Path) -> str:
    """Classify text into a routing decision.

    Returns:
        domain_key   — matched domain key in config.domain_notebooks
        "local"      — low but nonzero confidence, route to local notebook
        "NEW:<name>" — no domain matches, infer a name for new domain suggestion
    """
    cfg = load_project_config(project_path)
    domain_notebooks = cfg.get("domain_notebooks", {})

    if not domain_notebooks:
        return "local"

    tokens = _tokenize(text)
    if not tokens:
        return "local"

    scores: dict[str, float] = {}
    for key, nb in domain_notebooks.items():
        keywords = [kw.lower() for kw in nb.get("keywords", [])]
        if not keywords:
            continue
        matches = sum(1 for kw in keywords if _matches(kw, tokens))
        scores[key] = matches / len(tokens)

    if not scores:
        return "local"

    best_key = max(scores, key=lambda k: scores[k])
    best_score = scores[best_key]

    if best_score >= _HIGH_THRESHOLD:
        return best_key
    elif best_score >= _LOW_THRESHOLD:
        return "local"
    else:
        name = _infer_domain_name(tokens)
        return f"NEW:{name}"


def _tokenize(text: str) -> list[str]:
    """Extract meaningful lowercase tokens, filtering stop words."""
    raw = re.findall(r"[a-zA-Z]{2,}|[一-鿿]{2,}", text)
    return [t.lower() for t in raw if t.lower() not in _STOP_WORDS]


def _matches(keyword: str, tokens: list[str]) -> bool:
    """Bidirectional substring match: keyword in token OR token in keyword."""
    kw = keyword.lower()
    return any(kw in tok or tok in kw for tok in tokens)


def _infer_domain_name(tokens: list[str]) -> str:
    """Build a candidate domain name from the most specific (longest) tokens."""
    technical = sorted([t for t in tokens if len(t) >= 4], key=len, reverse=True)[:3]
    chosen = technical or tokens[:2]
    return " ".join(t.title() for t in chosen) if chosen else "New Domain"
