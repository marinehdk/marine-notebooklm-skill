import json
import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib.registry import (
    load_project_config, save_project_config,
    load_global_config, save_global_config,
    find_notebook_ids,
    load_notebooks_cache, save_notebooks_cache,
    _resolve_local_id, _resolve_global_ids,
)
from datetime import datetime, timedelta


def test_load_project_config_missing(tmp_path):
    config = load_project_config(tmp_path)
    assert config == {}


def test_save_and_load_project_config(tmp_path):
    cfg = {"local_notebook_id": "abc-123", "global_notebook_ids": ["def-456"]}
    save_project_config(tmp_path, cfg)
    loaded = load_project_config(tmp_path)
    assert loaded == cfg


def test_project_config_creates_nlm_dir(tmp_path):
    save_project_config(tmp_path, {"local_notebook_id": "x"})
    assert (tmp_path / ".nlm" / "config.json").exists()


def test_load_global_config_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("NLM_HOME", str(tmp_path))
    config = load_global_config()
    assert config == {"notebooks": []}


def test_save_and_load_global_config(tmp_path, monkeypatch):
    monkeypatch.setenv("NLM_HOME", str(tmp_path))
    cfg = {"notebooks": [{"id": "abc", "name": "test", "domain": "general"}]}
    save_global_config(cfg)
    loaded = load_global_config()
    assert loaded == cfg


def test_find_notebook_ids_local_new_schema(tmp_path):
    save_project_config(tmp_path, {
        "local_notebook": {"id": "local-id", "title": "My NB"},
        "global_notebooks": [],
    })
    assert find_notebook_ids("local", tmp_path) == ["local-id"]


def test_find_notebook_ids_global_new_schema(tmp_path):
    save_project_config(tmp_path, {
        "local_notebook": None,
        "global_notebooks": [{"id": "g1"}, {"id": "g2"}],
    })
    assert find_notebook_ids("global", tmp_path) == ["g1", "g2"]


def test_find_notebook_ids_auto_returns_local_first_new_schema(tmp_path):
    save_project_config(tmp_path, {
        "local_notebook": {"id": "local-id", "title": "Local"},
        "global_notebooks": [{"id": "g1"}],
    })
    result = find_notebook_ids("auto", tmp_path)
    assert result[0] == "local-id"
    assert "g1" in result


def test_find_notebook_ids_old_schema_migration(tmp_path):
    """旧格式 config 仍能正常读取（向前兼容）。"""
    save_project_config(tmp_path, {
        "local_notebook_id": "old-local",
        "global_notebook_ids": ["old-g1"],
    })
    result = find_notebook_ids("auto", tmp_path)
    assert result == ["old-local", "old-g1"]


def test_load_notebooks_cache_missing(tmp_path):
    result = load_notebooks_cache(tmp_path)
    assert result is None


def test_save_and_load_notebooks_cache(tmp_path):
    notebooks = [{"id": "abc", "title": "Test", "source_count": 5, "description": "", "created_at": "2026-01-01"}]
    save_notebooks_cache(tmp_path, notebooks)
    result = load_notebooks_cache(tmp_path)
    assert result is not None
    assert result["ttl_hours"] == 24
    assert result["notebooks"] == notebooks
    assert (tmp_path / ".nlm" / "notebooks_cache.json").exists()


def test_load_notebooks_cache_expired(tmp_path):
    notebooks = [{"id": "abc", "title": "Test", "source_count": 0, "description": "", "created_at": ""}]
    save_notebooks_cache(tmp_path, notebooks)
    # 伪造缓存写入时间为 25 小时前
    cache_file = tmp_path / ".nlm" / "notebooks_cache.json"
    data = json.loads(cache_file.read_text())
    stale_time = (datetime.now() - timedelta(hours=25)).isoformat(timespec="seconds")
    data["cached_at"] = stale_time
    cache_file.write_text(json.dumps(data))
    result = load_notebooks_cache(tmp_path)
    assert result is None


def test_resolve_local_id_new_schema():
    config = {"local_notebook": {"id": "new-id", "title": "Test"}}
    assert _resolve_local_id(config) == "new-id"


def test_resolve_local_id_old_schema():
    config = {"local_notebook_id": "old-id"}
    assert _resolve_local_id(config) == "old-id"


def test_resolve_local_id_empty():
    assert _resolve_local_id({}) is None


def test_resolve_global_ids_new_schema():
    config = {"global_notebooks": [{"id": "g1"}, {"id": "g2"}]}
    assert _resolve_global_ids(config) == ["g1", "g2"]


def test_resolve_global_ids_old_schema():
    config = {"global_notebook_ids": ["g1", "g2"]}
    assert _resolve_global_ids(config) == ["g1", "g2"]


def test_resolve_global_ids_empty():
    assert _resolve_global_ids({}) == []
