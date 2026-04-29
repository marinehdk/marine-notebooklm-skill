"""Tests for _score_keywords and score_and_prune_sources behaviour."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib.client import _score_keywords


def test_empty_source_keywords_returns_half():
    """GAP-1: empty keywords must return 0.5 (fallback keep), not 0.0 (delete)."""
    weights = {"COLREGs": 1.0, "collision": 0.5}
    assert _score_keywords([], weights) == 0.5


def test_empty_topic_weights_returns_half():
    """Existing behaviour: empty topic_weights → 0.5 neutral."""
    assert _score_keywords(["COLREGs", "routing"], {}) == 0.5


def test_matching_keywords_returns_positive():
    weights = {"COLREGs": 1.0}
    score = _score_keywords(["COLREGs avoidance"], weights)
    assert score > 0


def test_no_match_returns_zero():
    weights = {"COLREGs": 1.0}
    score = _score_keywords(["deep learning"], weights)
    assert score == 0.0


def test_score_capped_at_one():
    weights = {"nav": 1.0, "path": 1.0}
    score = _score_keywords(["nav path planning"], weights)
    assert score <= 1.0
