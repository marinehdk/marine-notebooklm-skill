"""Project name detection from filesystem and git."""

from __future__ import annotations
from pathlib import Path
import re


class ProjectDetector:
    """Detects project identity from filesystem paths."""

    def detect_from_path(self, project_path: Path) -> str:
        """Return 'workspace(branch)' or 'workspace'.

        Args:
            project_path: Path to the project directory.

        Returns:
            Project name in format: workspace(branch) or workspace
        """
        project_path = project_path.resolve()
        workspace_name = self._workspace_name_from_path(project_path)
        if not workspace_name:
            workspace_name = project_path.name
        branch = self._git_branch(project_path)
        if branch:
            return f"{workspace_name}({branch})"
        return workspace_name

    def _workspace_name_from_path(self, path: Path) -> str:
        """Extract workspace name from paths like /a/b/conductor/workspaces/sinan/."""
        path_str = str(path)
        # Match: .../conductor/workspaces/{workspace_name}
        match = re.search(r"conductor/workspaces/([^/]+)", path_str)
        if match:
            return match.group(1)
        return ""

    def _git_branch(self, path: Path) -> str:
        """Detect git branch from project path.

        Handles both regular repos and git worktrees (where .git is a file
        pointing to the actual gitdir).

        Returns only the branch name portion after the last '/'.
        E.g. 'marinehdk/sofia' → 'sofia', 'main' → 'main'.
        """
        git_dot_git = path / ".git"
        if git_dot_git.is_file():
            # Worktree: .git is a file containing "gitdir: /path/to/actual/.git"
            content = git_dot_git.read_text().strip()
            m = re.match(r"gitdir: (.+)", content)
            if m:
                git_head = Path(m.group(1)) / "HEAD"
            else:
                return ""
        else:
            git_head = git_dot_git / "HEAD"

        if git_head.exists():
            content = git_head.read_text().strip()
            m = re.match(r"ref: refs/heads/(.+)", content)
            if m:
                full = m.group(1)
                return full.split("/")[-1]
        return ""