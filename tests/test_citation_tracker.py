"""Tests for CitationTracker persistence and scoring."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
from lib.citation_tracker import CitationTracker


@pytest.fixture
def tmp_project(tmp_path):
    (tmp_path / ".nlm").mkdir()
    return tmp_path


def test_record_citations_increments_count(tmp_project):
    tracker = CitationTracker(tmp_project)
    tracker.record_citations([
        {"source_id": "abc123", "text": "some text"},
        {"source_id": "abc123", "text": "other text"},
        {"source_id": "def456", "text": "another"},
    ])
    counts = tracker.all_citation_counts()
    assert counts["abc123"] == 2
    assert counts["def456"] == 1


def test_record_citations_skips_missing_source_id(tmp_project):
    tracker = CitationTracker(tmp_project)
    tracker.record_citations([{"text": "no source_id here"}])
    assert tracker.all_citation_counts() == {}


def test_record_cited_urls_accumulates(tmp_project):
    tracker = CitationTracker(tmp_project)
    tracker.record_cited_urls({"https://arxiv.org/a", "https://imo.org/b"})
    tracker.record_cited_urls({"https://imo.org/b", "https://new.com/c"})
    data = tracker._load()
    cited = set(data["cited_urls"])
    assert cited == {"https://arxiv.org/a", "https://imo.org/b", "https://new.com/c"}


def test_citation_freq_score_normalises(tmp_project):
    tracker = CitationTracker(tmp_project)
    counts = {"src-a": 10, "src-b": 5, "src-c": 2}
    assert tracker.citation_freq_score("src-a", counts) == pytest.approx(1.0)
    assert tracker.citation_freq_score("src-b", counts) == pytest.approx(0.5)
    assert tracker.citation_freq_score("unknown", counts) == pytest.approx(0.0)


def test_citation_freq_score_empty_counts(tmp_project):
    tracker = CitationTracker(tmp_project)
    assert tracker.citation_freq_score("src-a", {}) == 0.0


def test_cited_in_report_score(tmp_project):
    tracker = CitationTracker(tmp_project)
    tracker.record_cited_urls({"https://arxiv.org/abs/1234"})
    assert tracker.cited_in_report_score("https://arxiv.org/abs/1234") == 1.0
    assert tracker.cited_in_report_score("https://arxiv.org/abs/1234/") == 1.0  # trailing slash
    assert tracker.cited_in_report_score("https://other.com/paper") == 0.0
    assert tracker.cited_in_report_score("") == 0.0


def test_missing_stats_file_returns_empty(tmp_project):
    tracker = CitationTracker(tmp_project)
    assert tracker.all_citation_counts() == {}


def test_corrupted_stats_file_returns_empty(tmp_project):
    stats_path = tmp_project / ".nlm" / "citation_stats.json"
    stats_path.write_text("not valid json")
    tracker = CitationTracker(tmp_project)
    assert tracker.all_citation_counts() == {}


def test_persistence_across_instances(tmp_project):
    CitationTracker(tmp_project).record_citations([{"source_id": "s1", "text": "x"}])
    counts = CitationTracker(tmp_project).all_citation_counts()
    assert counts.get("s1") == 1
