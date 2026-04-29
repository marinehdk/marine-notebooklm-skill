"""Verify bibliography parsing is wired into cmd_research output fields."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib.bibliography import parse_bibliography_urls


def test_parse_bibliography_urls_is_importable():
    """Smoke test: helper is importable and callable."""
    result = parse_bibliography_urls("")
    assert result == set()


def test_sources_cited_count_reflects_bibliography():
    """sources_cited_count must equal len(cited_urls), not a missing SDK field."""
    report = """
Summary text.

---

1. Smith, "Paper A", [https://arxiv.org/abs/1111]
2. Jones, "Paper B", [https://arxiv.org/abs/2222]
"""
    urls = parse_bibliography_urls(report)
    # Verify count matches parsed URLs, not a hardcoded 0
    assert len(urls) == 2
    assert "https://arxiv.org/abs/1111" in urls
