"""Manages project-to-notebook mappings stored in projects.json."""

from __future__ import annotations
import fcntl
import json
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional
from datetime import datetime


@dataclass
class NotebookRef:
    """Reference to a NotebookLM notebook."""
    url: str
    name: str
    id: str = ""  # extracted from URL if not provided
    description: str = ""
    topics: list = field(default_factory=list)
    domains: list = field(default_factory=list)  # e.g. ["compliance", "architecture"]

    def __post_init__(self):
        if not self.id and self.url:
            # Extract notebook ID from URL
            # URL format: https://notebooklm.google.com/notebook/xxxxx
            parts = self.url.rstrip("/").split("/")
            if parts:
                self.id = parts[-1]


@dataclass
class ProjectConfig:
    """Configuration for a single project."""
    name: str
    global_ref_notebooks: list[NotebookRef] = field(default_factory=list)
    local_notebooks: list[NotebookRef] = field(default_factory=list)
    created_at: str = ""
    description: str = ""
    last_research: dict = field(default_factory=dict)
    # last_research structure: {"task_id": "...", "source_ids": [...], "timestamp": "...", "query": "..."}

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        # Ensure NotebookRef objects
        self.global_ref_notebooks = [
            n if isinstance(n, NotebookRef) else NotebookRef(**n)
            for n in self.global_ref_notebooks
        ]
        self.local_notebooks = [
            n if isinstance(n, NotebookRef) else NotebookRef(**n)
            for n in self.local_notebooks
        ]


class NotebookRegistry:
    """Manages the registry of projects and their notebook configurations."""

    PROJECTS_FILE = "projects.json"

    def __init__(self, base_path: Optional[Path] = None):
        if base_path is None:
            base_path = Path(__file__).parent.parent.parent / "data"
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.projects_file = self.base_path / self.PROJECTS_FILE
        self.projects: dict[str, ProjectConfig] = {}
        self.load()

    def load(self):
        """Load projects from disk."""
        if not self.projects_file.exists():
            self.projects = {}
            return
        with open(self.projects_file, "r") as f:
            fcntl.flock(f, fcntl.LOCK_SH)
            try:
                data = json.load(f)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
        self.projects = {
            name: ProjectConfig(**vals)
            for name, vals in data.get("projects", {}).items()
        }

    def save(self):
        """Save projects to disk with exclusive file lock."""
        data = {
            "projects": {
                name: {
                    "name": cfg.name,
                    "global_ref_notebooks": [
                        asdict(n) for n in cfg.global_ref_notebooks
                    ],
                    "local_notebooks": [
                        asdict(n) for n in cfg.local_notebooks
                    ],
                    "created_at": cfg.created_at,
                    "description": cfg.description,
                    "last_research": cfg.last_research,
                }
                for name, cfg in self.projects.items()
            },
            "version": "1.0",
        }
        tmp_file = self.projects_file.with_suffix(".tmp")
        with open(tmp_file, "w") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                json.dump(data, f, indent=2)
                f.flush()
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
        tmp_file.replace(self.projects_file)

    def add_project(
        self,
        project_name: str,
        global_refs: list[dict],
        local_notebooks: list[dict],
        description: str = "",
    ) -> ProjectConfig:
        """Add or update a project configuration."""
        cfg = ProjectConfig(
            name=project_name,
            global_ref_notebooks=[NotebookRef(**r) for r in global_refs],
            local_notebooks=[NotebookRef(**n) for n in local_notebooks],
            description=description,
        )
        self.projects[project_name] = cfg
        self.save()
        return cfg

    def get_project(self, project_name: str) -> Optional[ProjectConfig]:
        return self.projects.get(project_name)

    def list_projects(self) -> list[str]:
        return list(self.projects.keys())

    def remove_project(self, project_name: str) -> bool:
        if project_name in self.projects:
            del self.projects[project_name]
            self.save()
            return True
        return False

    def update_last_research(
        self,
        project_name: str,
        task_id: str,
        source_ids: list[str],
        query: str,
    ):
        """Record the latest research task results for scope filtering."""
        project = self.get_project(project_name)
        if project:
            project.last_research = {
                "task_id": task_id,
                "source_ids": source_ids,
                "query": query,
                "timestamp": datetime.now().isoformat(),
            }
            self.save()

    def get_all_notebooks(self, project_name: str) -> list[NotebookRef]:
        """Get all notebooks (global + local) for a project."""
        project = self.get_project(project_name)
        if not project:
            return []
        return list(project.global_ref_notebooks) + list(project.local_notebooks)

    def append_notebooks_to_project(
        self,
        project_name: str,
        global_refs: list[dict] = None,
        local_notebooks: list[dict] = None,
    ) -> Optional[ProjectConfig]:
        """Append notebooks to an existing project (idempotent, no duplicates by id).

        Args:
            project_name: Name of the project to update.
            global_refs: List of NotebookRef dicts to append to global_ref_notebooks.
            local_notebooks: List of NotebookRef dicts to append to local_notebooks.

        Returns:
            Updated ProjectConfig, or None if project doesn't exist.
        """
        if project_name not in self.projects:
            return None
        cfg = self.projects[project_name]

        def _append_to_list(
            existing: list[NotebookRef], new: list[dict]
        ) -> list[NotebookRef]:
            existing_ids = {n.id for n in existing}
            result = list(existing)
            for r in new:
                ref = NotebookRef(**r) if isinstance(r, dict) else r
                if ref.id and ref.id not in existing_ids:
                    result.append(ref)
            return result

        if global_refs:
            cfg.global_ref_notebooks = _append_to_list(cfg.global_ref_notebooks, global_refs)
        if local_notebooks:
            cfg.local_notebooks = _append_to_list(cfg.local_notebooks, local_notebooks)

        self.save()
        return cfg
