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


def test_find_notebook_ids_local(tmp_path):
    save_project_config(tmp_path, {"local_notebook_id": "local-id", "global_notebook_ids": []})
    result = find_notebook_ids("local", tmp_path)
    assert result == ["local-id"]


def test_find_notebook_ids_global(tmp_path, monkeypatch):
    monkeypatch.setenv("NLM_HOME", str(tmp_path))
    save_global_config({"notebooks": [{"id": "g1"}, {"id": "g2"}]})
    result = find_notebook_ids("global", tmp_path)
    assert result == ["g1", "g2"]


def test_find_notebook_ids_auto_returns_local_first(tmp_path, monkeypatch):
    monkeypatch.setenv("NLM_HOME", str(tmp_path))
    save_project_config(tmp_path, {"local_notebook_id": "local-id", "global_notebook_ids": []})
    save_global_config({"notebooks": [{"id": "g1"}]})
    result = find_notebook_ids("auto", tmp_path)
    assert result[0] == "local-id"


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
