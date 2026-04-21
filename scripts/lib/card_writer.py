"""Write research/dialog results as knowledge card files."""

from __future__ import annotations
import re
from datetime import datetime
from pathlib import Path


CATEGORY_MAP = {
    "compliance": "ccs-compliance",
    "safety": "alm-pcf-mrc",
    "performance": "cuda",
    "middleware": "ros2",
    "architecture": "architecture",
    "vro": "algorithms",
    "berth": "algorithms",
    "ukc": "algorithms",
    "colav": "algorithms",
    "vpm": "vpm",
    "sensor": "architecture",
    "general": "algorithms",
}


class CardWriter:
    """Generate knowledge card markdown files from research results."""

    def write(
        self,
        question: str,
        answer: str,
        citations: list,
        category: str,
        output_dir: Path,
        notebooks_queried: list[str] = None,
        tags: list[str] = None,
    ) -> Path:
        """Write a knowledge card file.

        Returns the path to the created file.
        """
        # Resolve category directory
        dir_name = CATEGORY_MAP.get(category, category)
        target_dir = output_dir / dir_name
        target_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename
        date_str = datetime.now().strftime("%Y%m%d")
        slug = self._slugify(question)
        filename = f"{date_str}-{slug}.md"
        filepath = target_dir / filename

        # Build card content
        lines = [
            f"# {question[:100]}",
            "",
            f"**Category**: {category}",
            f"**Date**: {datetime.now().strftime('%Y-%m-%d')}",
        ]

        if notebooks_queried:
            lines.append(f"**Source notebooks**: {', '.join(notebooks_queried)}")
        if tags:
            lines.append(f"**Tags**: {' '.join(f'#{t}' for t in tags)}")

        lines.extend([
            "",
            "## Question",
            "",
            question,
            "",
            "## Answer",
            "",
            answer,
            "",
        ])

        if citations:
            lines.append("## Citations")
            lines.append("")
            for i, cite in enumerate(citations, 1):
                if isinstance(cite, dict):
                    text = cite.get("text", cite.get("excerpt", str(cite)))
                    source = cite.get("source_title", cite.get("id", ""))
                    lines.append(f"{i}. [{source}] {text}")
                else:
                    lines.append(f"{i}. {cite}")
            lines.append("")

        content = "\n".join(lines)
        filepath.write_text(content, encoding="utf-8")
        return filepath

    def _slugify(self, text: str, max_len: int = 50) -> str:
        """Convert text to a URL-friendly slug."""
        text = text.lower().strip()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[\s_]+", "-", text)
        text = re.sub(r"-+", "-", text)
        return text[:max_len].rstrip("-")
