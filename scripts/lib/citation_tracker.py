"""Citation frequency tracker for NLM scoring system.

Accumulates per-source citation counts from ask() ChatReference results
and maintains the set of URLs cited in deep research reports.

Storage: {project_path}/.nlm/citation_stats.json
Schema: spec §4.1.4
"""
from __future__ import annotations

import json
import time
from pathlib import Path


class CitationTracker:
    """Persist and query citation frequency signals for source scoring."""

    def __init__(self, project_path: Path) -> None:
        self._path = Path(project_path) / ".nlm" / "citation_stats.json"

    def record_citations(self, citations: list[dict]) -> None:
        """Increment citation count for each source_id in an ask() citations list."""
        data = self._load()
        now = int(time.time())
        for cite in citations:
            source_id = cite.get("source_id")
            if not source_id:
                continue
            entry = data["citation_freq"].setdefault(
                source_id,
                {"count": 0, "first_cited_at": now, "last_cited_at": now},
            )
            entry["count"] += 1
            entry["last_cited_at"] = now
        self._save(data)

    def record_cited_urls(self, urls: set[str]) -> None:
        """Persist the set of URLs cited in a deep research report bibliography."""
        data = self._load()
        existing = set(data.get("cited_urls", []))
        existing.update(urls)
        data["cited_urls"] = sorted(existing)
        self._save(data)

    def all_citation_counts(self) -> dict[str, int]:
        """Return {source_id: total_citation_count} for all tracked sources."""
        return {
            sid: v["count"]
            for sid, v in self._load().get("citation_freq", {}).items()
        }

    def citation_freq_score(self, source_id: str, all_counts: dict[str, int]) -> float:
        """Normalised citation frequency for source_id in [0, 1].

        Returns 0.0 when all_counts is empty or source has no history.
        """
        if not all_counts:
            return 0.0
        max_count = max(all_counts.values())
        if max_count == 0:
            return 0.0
        return all_counts.get(source_id, 0) / max_count

    def cited_in_report_score(self, source_url: str) -> float:
        """1.0 if URL was cited in any recorded deep research report, else 0.0."""
        if not source_url:
            return 0.0
        data = self._load()
        normalised = source_url.rstrip("/").lower()
        cited = {u.rstrip("/").lower() for u in data.get("cited_urls", [])}
        return 1.0 if normalised in cited else 0.0

    def _load(self) -> dict:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text())
            except Exception:
                pass
        return {"version": 1, "citation_freq": {}, "cited_urls": []}

    def _save(self, data: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
