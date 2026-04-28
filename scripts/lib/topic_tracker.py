"""Topic profile tracker for notebook-level relevance scoring.

Records ask queries and research topics per project. Used by the source scorer
to identify and prune low-relevance imports.

Storage: {project_path}/.nlm/topics.json
"""

import json
import re
import time
from pathlib import Path

# Common stop words to filter from keyword extraction
_STOP_ZH = {
    "的", "了", "是", "在", "我", "有", "和", "就", "不", "人", "都",
    "一", "上", "也", "与", "对", "从", "为", "以", "及", "但",
}
_STOP_EN = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "of", "in", "on", "at", "to",
    "for", "with", "by", "from", "as", "and", "or", "but", "not",
    "this", "that", "what", "which", "who", "how", "its", "it",
}
_STOP = _STOP_ZH | _STOP_EN

# Weight assigned per entry type
WEIGHT_ASK = 1.0       # /nlm-ask query
WEIGHT_RESEARCH = 2.0  # /nlm-research topic (more intentional)

# Recency half-life in days: recent topics count more
_HALF_LIFE_DAYS = 30.0


def _extract_keywords(text: str) -> list[str]:
    """Extract meaningful tokens from a query/topic string."""
    tokens = re.split(r"[\s,，。.、/\\|；;：:]+", text.strip())
    result = []
    for t in tokens:
        t = t.strip()
        if len(t) >= 2 and t.lower() not in _STOP:
            result.append(t)
    # Include the full phrase for phrase-level matching
    phrase = text.strip()
    if len(phrase) >= 4 and phrase not in result:
        result.append(phrase)
    # Deduplicate while preserving order
    seen: set[str] = set()
    deduped = []
    for k in result:
        if k.lower() not in seen:
            seen.add(k.lower())
            deduped.append(k)
    return deduped


class TopicTracker:
    """Per-project topic profile accumulated from ask/research interactions."""

    def __init__(self, project_path: str | Path):
        self._path = Path(project_path) / ".nlm" / "topics.json"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_ask(self, question: str) -> None:
        """Record an /nlm-ask query (weight=1)."""
        self._append(question, WEIGHT_ASK)

    def record_research(self, topic: str) -> None:
        """Record an /nlm-research topic (weight=2, more intentional signal)."""
        self._append(topic, WEIGHT_RESEARCH)

    def keyword_weights(self) -> dict[str, float]:
        """Return {keyword_lower: cumulative_weight} with recency decay.

        Returns an empty dict if no topics have been recorded yet.
        Callers should treat empty dict as "no profile → skip scoring".
        """
        data = self._load()
        now = int(time.time())
        weights: dict[str, float] = {}

        for entry in data.get("entries", []):
            age_days = (now - entry.get("ts", now)) / 86400.0
            # Exponential decay: weight halves every _HALF_LIFE_DAYS days
            recency = max(0.05, 2.0 ** (-age_days / _HALF_LIFE_DAYS))
            effective = entry["weight"] * recency

            for kw in entry.get("keywords", []):
                kl = kw.lower()
                weights[kl] = weights.get(kl, 0.0) + effective

        return weights

    def score_source_keywords(self, source_keywords: list[str]) -> float:
        """Score a source's keywords against the accumulated topic profile.

        Returns a float in [0.0, 1.0]:
        - 0.5  → no profile yet (neutral, don't prune)
        - 0.0  → zero overlap with any tracked topic
        - 1.0  → full overlap

        Matching is bidirectional substring: a source keyword "COLREGs 避碰"
        counts as a hit for topic keyword "避碰", and vice versa.
        """
        profile = self.keyword_weights()
        if not profile:
            return 0.5  # no data → neutral

        total = sum(profile.values())
        if total == 0.0:
            return 0.5

        source_lower = [k.lower() for k in source_keywords if k]
        matched = 0.0

        for topic_kw, w in profile.items():
            for src_kw in source_lower:
                if topic_kw in src_kw or src_kw in topic_kw:
                    matched += w
                    break  # each topic keyword counts at most once

        return min(1.0, matched / total)

    def summary(self) -> dict:
        """Return a human-readable summary of the current topic profile."""
        data = self._load()
        entries = data.get("entries", [])
        weights = self.keyword_weights()
        top = sorted(weights.items(), key=lambda x: -x[1])[:10]
        return {
            "total_entries": len(entries),
            "top_keywords": [{"keyword": k, "weight": round(w, 2)} for k, w in top],
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _append(self, text: str, weight: float) -> None:
        data = self._load()
        data["entries"].append({
            "text": text,
            "weight": weight,
            "ts": int(time.time()),
            "keywords": _extract_keywords(text),
        })
        self._save(data)

    def _load(self) -> dict:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"entries": []}

    def _save(self, data: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
