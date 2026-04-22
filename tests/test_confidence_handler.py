"""Tests for confidence_handler module."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib.confidence_handler import handle_confidence


def _high_result():
    return {"answer": "Detailed answer.", "confidence": "high", "source_notebook": "local"}


def _low_result():
    return {"answer": "Limited info.", "confidence": "low", "source_notebook": "local"}


# ── silent mode ────────────────────────────────────────────────────────────────

def test_silent_mode_returns_result_unchanged_on_low():
    result = handle_confidence(_low_result(), mode="silent", local_nb_id="nb-1", question="Q?")
    assert result["confidence"] == "low"
    assert "next_action" not in result


def test_silent_mode_high_confidence_unchanged():
    result = handle_confidence(_high_result(), mode="silent", local_nb_id="nb-1", question="Q?")
    assert "next_action" not in result


# ── prompt mode ────────────────────────────────────────────────────────────────

def test_prompt_mode_attaches_hint_without_calling_research():
    """mode=prompt must NOT call research — just attach a hint."""
    with patch("lib.confidence_handler.nlm_client") as mock_client:
        result = handle_confidence(_low_result(), mode="prompt", local_nb_id="nb-1", question="K8s ingress?")

    mock_client.research.assert_not_called()
    assert result.get("next_action", {}).get("type") == "suggest_research"
    assert "K8s ingress" in result["next_action"]["command"]


def test_prompt_mode_high_confidence_no_hint():
    with patch("lib.confidence_handler.nlm_client") as mock_client:
        result = handle_confidence(_high_result(), mode="prompt", local_nb_id="nb-1", question="Q?")

    mock_client.research.assert_not_called()
    assert "next_action" not in result


# ── research mode ─────────────────────────────────────────────────────────────

def test_research_mode_calls_research_and_retry():
    """mode=research should call research, import, and re-ask."""
    with patch("lib.confidence_handler.nlm_client") as mock_client:
        mock_client.research.return_value = {
            "status": "completed", "sources": [{"url": "x"}], "task_id": "t1"
        }
        mock_client.import_research_sources.return_value = [{"url": "x"}]
        mock_client.ask.return_value = {"answer": "Better answer.", "confidence": "high"}

        result = handle_confidence(_low_result(), mode="research", local_nb_id="nb-1", question="Q?")

    mock_client.research.assert_called_once()
    mock_client.ask.assert_called_once()
    assert result["confidence"] == "high"
    assert result.get("auto_researched") is True


def test_research_mode_import_error_does_not_propagate():
    """If import_research_sources raises, _research_and_retry must not crash."""
    with patch("lib.confidence_handler.nlm_client") as mock_client:
        mock_client.research.return_value = {
            "status": "completed", "sources": [{"url": "x"}], "task_id": "t1"
        }
        mock_client.import_research_sources.side_effect = Exception("RPC timeout")
        mock_client.ask.return_value = {"answer": "Answer after failed import.", "confidence": "medium"}

        # Must not raise
        result = handle_confidence(_low_result(), mode="research", local_nb_id="nb-1", question="Q?")

    assert result is not None
    assert result.get("auto_researched") is True


def test_research_mode_without_local_nb_id_falls_back_to_prompt():
    """If no local_nb_id, research mode cannot run — should fall back to hint."""
    with patch("lib.confidence_handler.nlm_client") as mock_client:
        result = handle_confidence(_low_result(), mode="research", local_nb_id=None, question="Q?")

    mock_client.research.assert_not_called()
    assert result.get("next_action", {}).get("type") == "suggest_research"
