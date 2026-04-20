import json
import os
from pathlib import Path


def _nlm_home() -> Path:
    if home := os.environ.get("NLM_HOME"):
        return Path(home)
    return Path.home() / ".nlm"


def load_project_config(project_path: Path) -> dict:
    config_file = Path(project_path) / ".nlm" / "config.json"
    if not config_file.exists():
        return {}
    return json.loads(config_file.read_text())


def save_project_config(project_path: Path, config: dict) -> None:
    nlm_dir = Path(project_path) / ".nlm"
    nlm_dir.mkdir(parents=True, exist_ok=True)
    (nlm_dir / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False))


def load_global_config() -> dict:
    global_file = _nlm_home() / "global.json"
    if not global_file.exists():
        return {"notebooks": []}
    return json.loads(global_file.read_text())


def save_global_config(config: dict) -> None:
    home = _nlm_home()
    home.mkdir(parents=True, exist_ok=True)
    (home / "global.json").write_text(json.dumps(config, indent=2, ensure_ascii=False))


def find_notebook_ids(scope: str, project_path: Path) -> list[str]:
    """Return ordered list of notebook IDs to try for given scope."""
    ids: list[str] = []

    if scope in ("local", "auto"):
        cfg = load_project_config(project_path)
        if local_id := cfg.get("local_notebook_id"):
            ids.append(local_id)

    if scope in ("global", "auto"):
        global_cfg = load_global_config()
        for nb in global_cfg.get("notebooks", []):
            if nb_id := nb.get("id"):
                ids.append(nb_id)

    return ids
