"""Extract cited URLs from the bibliography section of a deep research report.

Bibliography format (spec §4.1.2):
  After a \n---\n separator, numbered entries with [URL] at the end:
  1. Author et al., "Title", [https://example.com/paper]
"""
import re

_BIBLIO_ENTRY = re.compile(
    r'^\d+\.\s+.+,\s*\[(https?://[^\]]+)\]',
    re.MULTILINE,
)


def parse_bibliography_urls(report: str) -> set[str]:
    """Return the set of URLs cited in a research report's bibliography.

    Splits on the first \n---\n separator and extracts URLs from numbered
    entries matching: `N. ..., [https://...]`

    Returns an empty set when the report has no bibliography section.
    """
    if not report:
        return set()
    parts = report.split("\n---\n", maxsplit=1)
    if len(parts) < 2:
        return set()
    return {m.group(1) for m in _BIBLIO_ENTRY.finditer(parts[1])}
