"""Three-gate domain creation guard and merge/split detection.

Gate 1 — Minimum source queue  : source_count >= min_sources (default 20)
Gate 2 — Keyword overlap       : overlap with any existing domain < merge_overlap (default 40%)
Gate 3 — Total domain cap      : total_domains < max_domains (default 15)

Merge trigger : two domains share >40% keyword overlap AND combined sources < 200
Split trigger : a domain notebook has source_count > split_threshold (default 200)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .registry import load_project_config


@dataclass
class GuardResult:
    allowed: bool
    fallback: str                       # "local", "synthesis", or existing domain_key
    reason: str
    suggestion: str | None = None


@dataclass
class MergeSuggestion:
    merge_from: str
    merge_into: str
    overlap: float
    combined_sources: int
    command: str


@dataclass
class SplitSuggestion:
    domain: str
    source_count: int
    command: str
    reason: str


def check_new_domain(
    domain_name: str,
    domain_keywords: list[str],
    source_count: int,
    project_path: Path,
    *,
    min_sources: int = 20,
    max_domains: int = 15,
    merge_overlap: float = 0.40,
) -> GuardResult:
    """Run three-gate check before allowing a new domain notebook to be created.

    Args:
        domain_name: Human-readable name for the proposed domain.
        domain_keywords: Keywords that would define the new domain.
        source_count: Number of sources available to seed the new domain.
        project_path: Path to the project root (reads .nlm/config.json).
    """
    cfg = load_project_config(project_path)
    domain_notebooks = cfg.get("domain_notebooks", {})
    total_domains = len(domain_notebooks)

    # Gate 1: minimum source queue
    if source_count < min_sources:
        return GuardResult(
            allowed=False,
            fallback="local",
            reason=(
                f"source_count={source_count} < {min_sources} minimum. "
                "Routing to local notebook until more sources accumulate."
            ),
            suggestion=(
                f"Run /nlm-research on more '{domain_name}'-related topics "
                f"until {min_sources}+ sources are queued."
            ),
        )

    # Gate 2: keyword overlap with existing domains
    new_kws = {kw.lower() for kw in domain_keywords}
    for existing_key, existing_nb in domain_notebooks.items():
        existing_kws = {kw.lower() for kw in existing_nb.get("keywords", [])}
        if not existing_kws or not new_kws:
            continue
        overlap = len(new_kws & existing_kws) / max(len(new_kws | existing_kws), 1)
        if overlap >= merge_overlap:
            return GuardResult(
                allowed=False,
                fallback=existing_key,
                reason=(
                    f"Keyword overlap {overlap:.0%} with '{existing_key}' "
                    f">= {merge_overlap:.0%} threshold."
                ),
                suggestion=(
                    f"Route '{domain_name}' sources into '{existing_key}' "
                    "and update its keywords to cover the new subtopic."
                ),
            )

    # Gate 3: total domain cap
    if total_domains >= max_domains:
        return GuardResult(
            allowed=False,
            fallback="synthesis",
            reason=f"Domain count {total_domains} >= max {max_domains}.",
            suggestion=(
                "Review existing domains for merge opportunities "
                "before creating new ones."
            ),
        )

    return GuardResult(allowed=True, fallback="", reason="All gates passed.")


def check_merge_candidates(
    project_path: Path,
    *,
    merge_overlap: float = 0.40,
    combined_max: int = 200,
) -> list[MergeSuggestion]:
    """Find domain pairs that should be merged.

    Criteria: keyword overlap >= merge_overlap AND combined source count < combined_max.
    """
    cfg = load_project_config(project_path)
    domain_notebooks = cfg.get("domain_notebooks", {})
    suggestions: list[MergeSuggestion] = []

    keys = list(domain_notebooks.keys())
    for i, key_a in enumerate(keys):
        nb_a = domain_notebooks[key_a]
        kws_a = {kw.lower() for kw in nb_a.get("keywords", [])}
        count_a = nb_a.get("source_count", 0)

        for key_b in keys[i + 1:]:
            nb_b = domain_notebooks[key_b]
            kws_b = {kw.lower() for kw in nb_b.get("keywords", [])}
            count_b = nb_b.get("source_count", 0)

            if not kws_a or not kws_b:
                continue

            overlap = len(kws_a & kws_b) / max(len(kws_a | kws_b), 1)
            combined = count_a + count_b

            if overlap >= merge_overlap and combined < combined_max:
                suggestions.append(MergeSuggestion(
                    merge_from=key_b,
                    merge_into=key_a,
                    overlap=round(overlap, 2),
                    combined_sources=combined,
                    command=f"nlm setup --merge-domain {key_b} --into {key_a}",
                ))

    return suggestions


def check_split_candidates(
    project_path: Path,
    *,
    split_threshold: int = 200,
) -> list[SplitSuggestion]:
    """Find domain notebooks with source_count > split_threshold."""
    cfg = load_project_config(project_path)
    domain_notebooks = cfg.get("domain_notebooks", {})
    suggestions: list[SplitSuggestion] = []

    for key, nb in domain_notebooks.items():
        count = nb.get("source_count", 0)
        if count > split_threshold:
            suggestions.append(SplitSuggestion(
                domain=key,
                source_count=count,
                command=f"nlm setup --split-domain {key}",
                reason=(
                    f"Domain '{key}' has {count}/300 sources. "
                    "Consider splitting into sub-domains."
                ),
            ))

    return suggestions
