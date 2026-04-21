"""Route questions to the most appropriate notebooks based on domain detection."""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional


DOMAIN_RULES = [
    # (regex_pattern, domain, preferred_depth)
    (r"\bCOLREGs?\b|\bRule\s+\d+\b|\bIMO\b|\bSAR\b", "compliance", "deep"),
    (r"\bCCS\b|\bIACS\b|\bSIL[-\s]?\d?\b|\bIEC\s+615\d+\b", "compliance", "deep"),
    (r"\bWCET\b|\bread[-\s]?time\b|\blatency\b|\bCUDA\b", "performance", "deep"),
    (r"\bALM\b|\bH[123]\b|\bMRC\b|\bPCF\b", "safety", "deep"),
    (r"\bVRO\b|\bNSGA\b|\bweather\s+routing\b|\bvoyage\b", "vro", "auto"),
    (r"\bBERTH\b|\bMPC\b|\bdocking\b|\bberthing\b", "berth", "auto"),
    (r"\bUKC\b|\bsquat\b|\bdraft\b|\bunder\s+keel\b", "ukc", "auto"),
    (r"\bFastDDS\b|\bROS\s*2\b|\bQoS\b|\bSHM\b|\bDDS\b", "middleware", "fast"),
    (r"\bADR[-\s]?\d+\b|\barchitecture\b|\b5[-\s]?layer\b", "architecture", "deep"),
    (r"\bVPM\b|\bFossen\b|\bMMG\b|\b[34][-\s]?DOF\b", "vpm", "deep"),
    (r"\bCOLAV\b|\bcollision\s+avoid\b|\bDCPA\b|\bTCPA\b", "colav", "deep"),
    (r"\bESKF\b|\bsensor\s+fusion\b|\bEKF\b|\bIMU\b", "sensor", "auto"),
]


@dataclass
class RoutingDecision:
    """Result of domain-based notebook routing."""
    primary_notebook_ids: list[str] = field(default_factory=list)
    fallback_notebook_ids: list[str] = field(default_factory=list)
    matched_domain: str = "general"
    suggested_depth: str = "auto"
    confidence: float = 0.5


class DomainRouter:
    """Route questions to appropriate SINAN notebooks based on content analysis."""

    def route(self, question: str, available_notebooks: list) -> RoutingDecision:
        """Analyze question and return routing decision.

        Args:
            question: The user's question text.
            available_notebooks: List of NotebookRef objects (or dicts with 'id', 'domains').
        """
        # Detect domains
        matched_domains = []
        suggested_depth = "auto"

        for pattern, domain, depth in DOMAIN_RULES:
            if re.search(pattern, question, re.I):
                matched_domains.append(domain)
                if depth == "deep":
                    suggested_depth = "deep"

        if not matched_domains:
            # No specific domain detected — use all available notebooks
            all_ids = [self._get_id(nb) for nb in available_notebooks]
            return RoutingDecision(
                primary_notebook_ids=all_ids,
                matched_domain="general",
                suggested_depth="auto",
                confidence=0.3,
            )

        # Match notebooks by domain
        primary_ids = []
        fallback_ids = []

        for nb in available_notebooks:
            nb_domains = self._get_domains(nb)
            if any(d in nb_domains for d in matched_domains):
                primary_ids.append(self._get_id(nb))
            elif "all" in nb_domains:
                fallback_ids.append(self._get_id(nb))
            else:
                fallback_ids.append(self._get_id(nb))

        # If no primary match, promote fallbacks
        if not primary_ids:
            primary_ids = fallback_ids
            fallback_ids = []

        return RoutingDecision(
            primary_notebook_ids=primary_ids,
            fallback_notebook_ids=fallback_ids,
            matched_domain=matched_domains[0] if matched_domains else "general",
            suggested_depth=suggested_depth,
            confidence=min(len(matched_domains) * 0.3 + 0.4, 1.0),
        )

    def _get_id(self, nb) -> str:
        if isinstance(nb, dict):
            return nb.get("id", "")
        return getattr(nb, "id", "")

    def _get_domains(self, nb) -> list[str]:
        if isinstance(nb, dict):
            return nb.get("domains", [])
        return getattr(nb, "domains", [])
