import json
from pathlib import Path


def _storage_state_path() -> Path:
    return Path.home() / ".notebooklm" / "storage_state.json"


def is_authenticated() -> bool:
    """Check if user has valid NotebookLM authentication (must have SID cookie)."""
    path = _storage_state_path()
    if not path.exists():
        return False
    try:
        with open(path) as f:
            data = json.load(f)
        cookies = data.get("cookies", [])
        # Must have at least one cookie (SID is required)
        return len(cookies) > 0
    except Exception:
        return False


def assert_authenticated() -> None:
    """Exit with helpful message if not authenticated."""
    if not is_authenticated():
        print(
            "❌ Not authenticated with Google.\n"
            "Run: bash $HOME/.claude/skills/nlm/scripts/invoke.sh setup --auth"
        )
        raise SystemExit(1)
