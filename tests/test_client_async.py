"""Tests for async client functions (ask_async, research_async)."""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib.client import ask_async, research_async
from notebooklm.exceptions import NetworkError


def test_ask_async_returns_dict_with_answer_and_confidence():
    """Test ask_async returns same structure as sync ask()."""
    async def _run():
        mock_result = MagicMock()
        mock_result.answer = "This is a test answer."
        mock_result.references = [{"title": "Ref 1"}] * 3

        mock_chat_api = AsyncMock()
        mock_chat_api.ask = AsyncMock(return_value=mock_result)

        mock_client = AsyncMock()
        mock_client.chat = mock_chat_api
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("lib.client.NotebookLMClient") as MockClient:
            MockClient.from_storage = AsyncMock(return_value=mock_client)
            result = await ask_async("nb-123", "What is this?")

        assert "answer" in result
        assert "confidence" in result
        assert result["answer"] == "This is a test answer."
        assert result["confidence"] == "high"  # 3+ references = high

    asyncio.run(_run())


def test_ask_async_low_references_confidence():
    """Test ask_async returns low confidence with no references."""
    async def _run():
        mock_result = MagicMock()
        mock_result.answer = "This is a longer partial answer with enough characters."
        mock_result.references = []  # no refs = low

        mock_chat_api = AsyncMock()
        mock_chat_api.ask = AsyncMock(return_value=mock_result)

        mock_client = AsyncMock()
        mock_client.chat = mock_chat_api
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("lib.client.NotebookLMClient") as MockClient:
            MockClient.from_storage = AsyncMock(return_value=mock_client)
            result = await ask_async("nb-123", "What?")

        assert result["confidence"] == "low"

    asyncio.run(_run())


def test_ask_async_not_found_confidence():
    """Test ask_async returns not_found when answer is empty."""
    async def _run():
        mock_result = MagicMock()
        mock_result.answer = ""  # empty = not_found
        mock_result.references = []

        mock_chat_api = AsyncMock()
        mock_chat_api.ask = AsyncMock(return_value=mock_result)

        mock_client = AsyncMock()
        mock_client.chat = mock_chat_api
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("lib.client.NotebookLMClient") as MockClient:
            MockClient.from_storage = AsyncMock(return_value=mock_client)
            result = await ask_async("nb-123", "Unknown?")

        assert result["confidence"] == "not_found"

    asyncio.run(_run())


def test_ask_async_retries_on_network_error():
    """Test ask_async retries on NetworkError."""
    async def _run():
        mock_result = MagicMock()
        mock_result.answer = "Success after retry."
        mock_result.references = [{"title": "Ref 1"}] * 2

        mock_chat_api = AsyncMock()
        # First call fails, second succeeds
        mock_chat_api.ask = AsyncMock(
            side_effect=[NetworkError("Connection failed"), mock_result]
        )

        mock_client = AsyncMock()
        mock_client.chat = mock_chat_api
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("lib.client.NotebookLMClient") as MockClient:
            MockClient.from_storage = AsyncMock(return_value=mock_client)
            result = await ask_async("nb-123", "Retry test?", retries=2, retry_delay=0.1)

        assert result["answer"] == "Success after retry."
        assert mock_chat_api.ask.call_count == 2

    asyncio.run(_run())


def test_ask_async_raises_after_max_retries():
    """Test ask_async raises exception after exhausting retries."""
    async def _run():
        mock_chat_api = AsyncMock()
        mock_chat_api.ask = AsyncMock(side_effect=NetworkError("Persistent failure"))

        mock_client = AsyncMock()
        mock_client.chat = mock_chat_api
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("lib.client.NotebookLMClient") as MockClient:
            MockClient.from_storage = AsyncMock(return_value=mock_client)
            with pytest.raises(NetworkError):
                await ask_async("nb-123", "Fail test?", retries=1, retry_delay=0.1)

    asyncio.run(_run())


def test_research_async_returns_completed_status():
    """Test research_async returns completed after in_progress→completed transition."""
    async def _run():
        mock_research_api = AsyncMock()
        mock_research_api.start = AsyncMock(return_value={"task_id": "task-1"})
        # poll sequence: in_progress → completed (normal case)
        mock_research_api.poll = AsyncMock(side_effect=[
            {"status": "in_progress", "report": "", "sources": []},
            {"status": "completed", "report": "Research findings...", "sources": [{"url": "https://example.com"}]},
        ])

        mock_client = AsyncMock()
        mock_client.research = mock_research_api
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("lib.client.NotebookLMClient") as MockClient:
            with patch("lib.client.asyncio.sleep", new_callable=AsyncMock):
                MockClient.from_storage = AsyncMock(return_value=mock_client)
                result = await research_async("nb-123", "Python patterns", mode="fast")

        assert result["status"] == "completed"
        assert "report" in result
        assert "sources" in result
        assert "task_id" in result
        assert result["task_id"] == "task-1"

    asyncio.run(_run())


def test_research_async_skips_stale_completed_result():
    """If poll immediately returns completed (no in_progress seen), skip stale result."""
    async def _run():
        mock_research_api = AsyncMock()
        mock_research_api.start = AsyncMock(return_value={"task_id": "task-new"})
        # Stale: immediately completed, then times out (no in_progress ever)
        mock_research_api.poll = AsyncMock(
            return_value={"status": "completed", "report": "stale Vue results", "sources": []}
        )

        mock_client = AsyncMock()
        mock_client.research = mock_research_api
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        import time
        call_count = 0
        original_time = time.time

        # Force timeout after a few polls
        start_t = original_time()
        poll_results = [
            {"status": "completed", "report": "stale Vue", "sources": []},
            {"status": "completed", "report": "stale Vue", "sources": []},
        ]

        mock_research_api.poll = AsyncMock(side_effect=poll_results)

        with patch("lib.client.NotebookLMClient") as MockClient:
            with patch("lib.client.asyncio.sleep", new_callable=AsyncMock):
                with patch("lib.client.time") as mock_time:
                    # deadline passed after 2 polls
                    mock_time.time.side_effect = [start_t, start_t, start_t, start_t + 999]
                    MockClient.from_storage = AsyncMock(return_value=mock_client)
                    result = await research_async("nb-123", "Claude Code patterns", mode="fast", retries=0)

        # Should NOT return stale "completed" result — must be timeout
        assert result["status"] == "timeout", f"Expected timeout for stale result, got {result['status']}"
        assert "stale Vue" not in result.get("report", "")

    asyncio.run(_run())


def test_research_async_returns_error_on_failed_start():
    """Test research_async returns error status when start fails."""
    async def _run():
        mock_research_api = AsyncMock()
        mock_research_api.start = AsyncMock(return_value=None)

        mock_client = AsyncMock()
        mock_client.research = mock_research_api
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("lib.client.NotebookLMClient") as MockClient:
            MockClient.from_storage = AsyncMock(return_value=mock_client)
            result = await research_async("nb-123", "Topic", mode="fast")

        assert result["status"] == "error"
        assert result["report"] == ""
        assert result["sources"] == []

    asyncio.run(_run())


def test_research_async_retries_on_network_error():
    """Test research_async retries on NetworkError."""
    async def _run():
        mock_research_api = AsyncMock()
        # First call raises, second succeeds
        mock_research_api.start = AsyncMock(
            side_effect=[
                NetworkError("Connection failed"),
                {"task_id": "task-2"},
            ]
        )
        # Poll: in_progress → completed (required by stale-result fix)
        mock_research_api.poll = AsyncMock(side_effect=[
            {"status": "in_progress", "report": "", "sources": []},
            {"status": "completed", "report": "OK", "sources": []},
        ])

        mock_client = AsyncMock()
        mock_client.research = mock_research_api
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("lib.client.NotebookLMClient") as MockClient:
            with patch("lib.client.asyncio.sleep", new_callable=AsyncMock):
                MockClient.from_storage = AsyncMock(return_value=mock_client)
                result = await research_async("nb-123", "Topic", mode="fast", retries=1)

        assert result["status"] == "completed"
        assert mock_research_api.start.call_count == 2

    asyncio.run(_run())
