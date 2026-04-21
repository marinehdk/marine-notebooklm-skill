"""Source scope decision logic for the main agent."""

from __future__ import annotations
from enum import Enum
from dataclasses import dataclass
from typing import Optional


class SourceScope(Enum):
    """Scope of sources to query."""
    LATEST = "latest"   # Only sources from the most recent research task
    ALL = "all"         # All sources in the local notebook
    GLOBAL = "global"   # Include global reference notebooks too


@dataclass
class SourceSelector:
    """Decides which sources to query based on context."""

    def get_scope(self, scope_arg: Optional[str]) -> SourceScope:
        """Parse scope argument to SourceScope enum."""
        if scope_arg is None:
            return SourceScope.ALL
        scope_arg = scope_arg.lower().strip()
        if scope_arg in ("latest", "recent", "this"):
            return SourceScope.LATEST
        elif scope_arg == "global":
            return SourceScope.GLOBAL
        else:
            return SourceScope.ALL

    def select_sources(
        self,
        scope: SourceScope,
        all_source_ids: list[str],
        latest_source_ids: list[str],
        global_notebook_ids: list[str],
    ) -> tuple[list[str], bool]:
        """Select sources based on scope.

        Returns:
            (selected_source_ids, include_global)
        """
        if scope == SourceScope.LATEST:
            return latest_source_ids, False
        elif scope == SourceScope.GLOBAL:
            return all_source_ids, True
        else:  # ALL
            return all_source_ids, False
