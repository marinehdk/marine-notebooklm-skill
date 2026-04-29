import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib.bibliography import parse_bibliography_urls


REPORT_WITH_BIBLIOGRAPHY = """
Some research report content here.

---

1. Smith et al., "Path Planning", [https://arxiv.org/abs/1234.5678]
2. Jones, "COLREGs Analysis", [https://imo.org/papers/colregs]
3. No URL entry here, just text
4. Multi-word Title with (parens), [https://example.com/paper?id=99]
"""

REPORT_NO_SEPARATOR = "Just a plain report with no bibliography section."

REPORT_EMPTY = ""

MARKDOWN_LINK_FORMAT = """
Content

---

1. Title, [(https://wrong-format.com)]
2. Real entry, [https://correct.com/paper]
"""


def test_extracts_urls_from_bibliography():
    urls = parse_bibliography_urls(REPORT_WITH_BIBLIOGRAPHY)
    assert "https://arxiv.org/abs/1234.5678" in urls
    assert "https://imo.org/papers/colregs" in urls
    assert "https://example.com/paper?id=99" in urls


def test_ignores_entries_without_url():
    urls = parse_bibliography_urls(REPORT_WITH_BIBLIOGRAPHY)
    assert len(urls) == 3  # entry 3 has no URL bracket


def test_returns_empty_set_when_no_separator():
    assert parse_bibliography_urls(REPORT_NO_SEPARATOR) == set()


def test_returns_empty_set_for_empty_report():
    assert parse_bibliography_urls(REPORT_EMPTY) == set()


def test_returns_set_type():
    result = parse_bibliography_urls(REPORT_WITH_BIBLIOGRAPHY)
    assert isinstance(result, set)


def test_deduplicates_repeated_urls():
    report = """
Content

---

1. Entry A, [https://same.com/paper]
2. Entry B, [https://same.com/paper]
"""
    urls = parse_bibliography_urls(report)
    assert urls == {"https://same.com/paper"}
