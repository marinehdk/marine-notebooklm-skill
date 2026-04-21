"""Unified auth path resolution with multi-path fallback."""

from __future__ import annotations
import os
from pathlib import Path


# Auth state search order
AUTH_PATHS = [
    # 1. This skill's own browser state
    Path.home() / ".claude" / "skills" / "notebooklm-superpower" / "data" / "browser_state" / "state.json",
    # 2. Skill's local data dir (when running from source tree)
    Path(__file__).resolve().parent.parent.parent / "data" / "browser_state" / "state.json",
    # 3. notebooklm-skill shared auth (backward compat)
    Path.home() / ".claude" / "skills" / "notebooklm" / "data" / "browser_state" / "state.json",
]


def resolve_auth_path() -> Path:
    """Return the first existing auth state path, or the default path for creation."""
    # Check env override first
    env_path = os.getenv("NOTEBOOKLM_STATE_PATH")
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p

    for p in AUTH_PATHS:
        if p.exists():
            return p

    # Return the skill's own path (will be created during auth setup)
    return AUTH_PATHS[0]


def resolve_data_dir() -> Path:
    """Return the data directory for this skill."""
    # Prefer skill installation path
    installed = Path.home() / ".claude" / "skills" / "notebooklm-superpower" / "data"
    if installed.exists():
        return installed
    # Fallback to local source tree
    local = Path(__file__).resolve().parent.parent.parent / "data"
    local.mkdir(parents=True, exist_ok=True)
    return local
