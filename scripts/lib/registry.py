import json
import os
from datetime import datetime, timedelta
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


def _resolve_local_id(config: dict) -> str | None:
    """支持新 schema (local_notebook.id) 和旧 schema (local_notebook_id) 两种格式。"""
    if local_nb := config.get("local_notebook"):
        return local_nb.get("id")
    return config.get("local_notebook_id")


def _resolve_global_ids(config: dict) -> list[str]:
    """支持新 schema (global_notebooks[].id) 和旧 schema (global_notebook_ids) 两种格式。"""
    if global_nbs := config.get("global_notebooks"):
        return [nb.get("id") for nb in global_nbs if nb.get("id")]
    return config.get("global_notebook_ids", [])


def find_notebook_ids(scope: str, project_path: Path) -> list[str]:
    """Return ordered list of notebook IDs to try for given scope.

    Supports both new schema (local_notebook/global_notebooks objects)
    and old schema (local_notebook_id/global_notebook_ids strings) for migration.
    Global notebooks are now per-project (stored in .nlm/config.json).
    """
    ids: list[str] = []
    cfg = load_project_config(project_path)

    if scope in ("local", "auto"):
        if local_id := _resolve_local_id(cfg):
            ids.append(local_id)

    if scope in ("global", "auto"):
        ids.extend(_resolve_global_ids(cfg))

    return ids


def load_notebooks_cache(project_path: Path) -> dict | None:
    """返回有效缓存内容，不存在或已过期或损坏返回 None。TTL 默认 24h。"""
    cache_file = Path(project_path) / ".nlm" / "notebooks_cache.json"
    if not cache_file.exists():
        return None
    try:
        data = json.loads(cache_file.read_text())
        cached_at = datetime.fromisoformat(data["cached_at"])
        ttl = timedelta(hours=data.get("ttl_hours", 24))
        if datetime.now() - cached_at > ttl:
            return None
        return data
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def save_notebooks_cache(project_path: Path, notebooks: list[dict]) -> None:
    """将笔记本列表写入缓存，TTL 24h。"""
    nlm_dir = Path(project_path) / ".nlm"
    nlm_dir.mkdir(parents=True, exist_ok=True)
    (nlm_dir / "notebooks_cache.json").write_text(json.dumps({
        "cached_at": datetime.now().isoformat(timespec="seconds"),
        "ttl_hours": 24,
        "notebooks": notebooks,
    }, indent=2, ensure_ascii=False))
