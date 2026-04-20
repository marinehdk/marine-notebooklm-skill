import json
import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib.registry import (
    load_project_config, save_project_config,
    load_global_config, save_global_config,
    find_notebook_ids,
)


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
