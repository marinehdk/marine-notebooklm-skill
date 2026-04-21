"""Inter-skill context passing via temp files with TTL.

Allows one skill invocation to pass context (e.g. notebook_id, project_name,
last research results) to the next invocation without re-querying.

Context is stored as JSON in /tmp/nlm-ctx-<key>.json with a 1-hour TTL.
"""

from __future__ import annotations
import json
import os
import time
from pathlib import Path
from typing import Any, Optional

CTX_DIR = Path("/tmp")
CTX_PREFIX = "nlm-ctx-"
CTX_TTL_SECONDS = 3600  # 1 hour


def _ctx_path(key: str) -> Path:
    """Get the temp file path for a context key."""
    safe_key = key.replace("/", "_").replace(" ", "_")
    return CTX_DIR / f"{CTX_PREFIX}{safe_key}.json"


def set_context(key: str, data: dict[str, Any]) -> Path:
    """Store context data with timestamp. Returns the file path."""
    path = _ctx_path(key)
    payload = {
        "created_at": time.time(),
        "ttl": CTX_TTL_SECONDS,
        "data": data,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False))
    return path


def get_context(key: str) -> Optional[dict[str, Any]]:
    """Retrieve context data if it exists and hasn't expired."""
    path = _ctx_path(key)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text())
        created = payload.get("created_at", 0)
        ttl = payload.get("ttl", CTX_TTL_SECONDS)
        if time.time() - created > ttl:
            path.unlink(missing_ok=True)
            return None
        return payload.get("data")
    except (json.JSONDecodeError, KeyError):
        path.unlink(missing_ok=True)
        return None


def clear_context(key: str) -> bool:
    """Remove a context entry."""
    path = _ctx_path(key)
    if path.exists():
        path.unlink(missing_ok=True)
        return True
    return False


def cleanup_expired():
    """Remove all expired context files."""
    now = time.time()
    for f in CTX_DIR.glob(f"{CTX_PREFIX}*.json"):
        try:
            payload = json.loads(f.read_text())
            created = payload.get("created_at", 0)
            ttl = payload.get("ttl", CTX_TTL_SECONDS)
            if now - created > ttl:
                f.unlink(missing_ok=True)
        except Exception:
            f.unlink(missing_ok=True)


# Convenience: last-used notebook & project context
def save_session_context(
    project_name: str,
    notebook_id: str = "",
    last_question: str = "",
    extra: dict = None,
):
    """Save the current session's working context."""
    data = {
        "project_name": project_name,
        "notebook_id": notebook_id,
        "last_question": last_question,
    }
    if extra:
        data.update(extra)
    set_context("session", data)


def get_session_context() -> Optional[dict[str, Any]]:
    """Get the current session context."""
    return get_context("session")
