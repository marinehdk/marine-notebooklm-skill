"""Automatically decide research depth (fast vs deep) based on question analysis."""

from __future__ import annotations
import re
from dataclasses import dataclass


# Patterns that indicate complex, multi-angle questions
DEEP_PATTERNS = [
    re.compile(r"\bcompare\b.*\bvs\b|\bversus\b", re.I),
    re.compile(r"\bdesign\b|\barchitecture\b|\bapproach\b", re.I),
    re.compile(r"\bstrategy\b|\btrade-?off\b|\bpros\s*and\s*cons\b", re.I),
    re.compile(r"\bmulti[-\s]?tenant\b|\bpermission\b|\bauth(?:orization)?\b", re.I),
    re.compile(r"\bmigration\b|\brefactor(?:ing)?\b", re.I),
    re.compile(r"\bperformance\b.*\boptimi[sz]\b", re.I),
    re.compile(r"\bscalab(?:ility|le)\b", re.I),
    re.compile(r"\bimplement(?:ation)?\b.*\bfrom\s*scratch\b", re.I),
    re.compile(r"\bdecide\b.*\bbetween\b", re.I),
    re.compile(r"\bhow\s+(?:do\s+|should\s+)i\b", re.I),
    re.compile(r"\bwhy\s+(?:is|are|do|does)\b.*\binstead\b", re.I),
    re.compile(r"\bexplain\b.*\bdifference\b", re.I),
    # SINAN / Maritime domain patterns (always deep)
    re.compile(r"\bCOLREGs?\b|\bRule\s+\d+\b|\bIMO\b|\bSAR\b", re.I),
    re.compile(r"\bCCS\b|\bIACS\b|\bSIL[-\s]?\d?\b|\bFMEA\b", re.I),
    re.compile(r"\bWCET\b|\bread[-\s]?time\b|\blatency\b|\bjitter\b", re.I),
    re.compile(r"\bALM\b|\bH[123]\s+mode\b|\bMRC\b|\bPCF\b", re.I),
    re.compile(r"\bADR[-\s]?\d+\b|\b5[-\s]?layer\b", re.I),
    re.compile(r"\bVPM\b|\bFossen\b|\bMMG\b|\b[34][-\s]?DOF\b", re.I),
    re.compile(r"\bCOLAV\b|\bVRO\b|\bNSGA\b|\bUKC\b|\bBERTH\b", re.I),
    re.compile(r"\bFastDDS\b|\bSHM\b|\bSROS2\b|\bPREEMPT_RT\b", re.I),
]

# Patterns that indicate simple factual questions
FAST_PATTERNS = [
    re.compile(r"\bwhat\s+is\b.*\bversion\b", re.I),
    re.compile(r"\bwhen\s+did\b", re.I),
    re.compile(r"\bhow\s+many\b", re.I),
    re.compile(r"\blist\b.*\bexamples?\b", re.I),
    re.compile(r"\bwho\s+(?:is|was|were)\b", re.I),
    re.compile(r"\bdefine\b|\bmeaning\b|\bwhat\s+does\b", re.I),
    re.compile(r"\bsyntax\b|\bparameter\b|\boption\b", re.I),
]

# Question length threshold (longer questions tend to be more complex)
LENGTH_THRESHOLD = 80


@dataclass
class DepthDecision:
    """Result of depth analysis."""
    mode: str  # "fast" or "deep"
    reason: str
    confidence: float  # 0.0 to 1.0


class DepthDecider:
    """Decides research depth based on question analysis."""

    def decide(self, question: str) -> str:
        """Return 'fast' or 'deep'."""
        return self.analyze(question).mode

    def analyze(self, question: str) -> DepthDecision:
        """Return detailed depth decision."""
        deep_score = 0
        fast_score = 0

        for pattern in DEEP_PATTERNS:
            if pattern.search(question):
                deep_score += 1

        for pattern in FAST_PATTERNS:
            if pattern.search(question):
                fast_score += 1

        # Length factor
        if len(question) > LENGTH_THRESHOLD:
            deep_score += 0.5

        # Make decision
        if deep_score > fast_score:
            confidence = min(deep_score / 3.0, 1.0)
            return DepthDecision(
                mode="deep",
                reason=f"complex patterns detected (score: {deep_score})",
                confidence=confidence,
            )
        else:
            confidence = min(fast_score / 2.0, 1.0) if fast_score > 0 else 0.5
            return DepthDecision(
                mode="fast",
                reason=f"factual/simple patterns (score: {fast_score})",
                confidence=confidence,
            )
