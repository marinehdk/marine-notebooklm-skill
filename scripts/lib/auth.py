from pathlib import Path


def _storage_state_path() -> Path:
    return Path.home() / ".notebooklm" / "storage_state.json"


def is_authenticated() -> bool:
    return _storage_state_path().exists()


def assert_authenticated() -> None:
    """Exit with helpful message if not authenticated."""
    if not is_authenticated():
        print(
            "❌ Not authenticated with Google.\n"
            "Run: bash $HOME/.claude/skills/nlm/scripts/invoke.sh setup --auth"
        )
        raise SystemExit(1)
