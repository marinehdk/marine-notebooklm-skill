import asyncio
import time
from typing import Any

from notebooklm import NotebookLMClient


def _confidence(answer: str, references: list) -> str:
    if not answer or len(answer) < 20:
        return "not_found"
    if not references:
        return "low"
    if len(references) >= 3:
        return "high"
    return "medium"


def ask(notebook_id: str, question: str) -> dict[str, Any]:
    async def _run():
        async with await NotebookLMClient.from_storage() as client:
            result = await client.chat.ask(notebook_id, question)
            refs = [
                {"citation_number": r.citation_number, "text": (r.cited_text or "")[:200]}
                for r in (result.references or [])
            ]
            return {
                "answer": result.answer,
                "confidence": _confidence(result.answer, result.references),
                "citations": refs,
            }
    return asyncio.run(_run())


def list_notebooks() -> list[dict[str, Any]]:
    async def _run():
        from datetime import datetime
        from notebooklm.types import Notebook

        # The library's from_api_response uses data[5][5] (last-accessed time) as
        # created_at. The real creation timestamp is at data[5][8]. We patch once
        # for this call to capture the correct value.
        real_created: dict[str, datetime] = {}
        original = Notebook.from_api_response.__func__

        @classmethod  # type: ignore[misc]
        def _patched(cls, data):
            nb = original(cls, data)
            if len(data) > 5 and isinstance(data[5], list) and len(data[5]) > 8:
                ts = data[5][8]
                if isinstance(ts, list) and ts:
                    try:
                        real_created[nb.id] = datetime.fromtimestamp(ts[0])
                    except (TypeError, ValueError):
                        pass
            return nb

        Notebook.from_api_response = _patched
        try:
            async with await NotebookLMClient.from_storage() as client:
                nbs = await client.notebooks.list()
        finally:
            Notebook.from_api_response = original

        return [
            {
                "id":           nb.id,
                "title":        nb.title,
                "source_count": getattr(nb, "sources_count", 0),
                "description":  "",
                "created_at":   str(real_created.get(nb.id, getattr(nb, "created_at", ""))),
            }
            for nb in nbs
        ]
    return asyncio.run(_run())


def create_notebook(title: str) -> dict[str, Any]:
    async def _run():
        async with await NotebookLMClient.from_storage() as client:
            nb = await client.notebooks.create(title)
            return {"id": nb.id, "title": nb.title}
    return asyncio.run(_run())


def add_url(notebook_id: str, url: str) -> dict[str, Any]:
    async def _run():
        async with await NotebookLMClient.from_storage() as client:
            source = await client.sources.add_url(notebook_id, url, wait=True)
            return {"id": source.id, "title": getattr(source, "title", url)}
    return asyncio.run(_run())


def add_text(notebook_id: str, title: str, content: str) -> dict[str, Any]:
    async def _run():
        async with await NotebookLMClient.from_storage() as client:
            source = await client.sources.add_text(notebook_id, title, content, wait=True)
            return {"id": source.id, "title": title}
    return asyncio.run(_run())


def add_note(notebook_id: str, title: str, content: str) -> dict[str, Any]:
    async def _run():
        async with await NotebookLMClient.from_storage() as client:
            note = await client.notes.create(notebook_id, title=title, content=content)
            return {"id": note.id, "title": note.title}
    return asyncio.run(_run())


def research(notebook_id: str, topic: str, mode: str = "fast") -> dict[str, Any]:
    """Start research and poll until complete. Returns report + sources.

    NOTE: deep research can take 120-180s. Adjust timeout accordingly.
    fast: 60s timeout, 3s poll interval
    deep: 180s timeout, 5s poll interval
    """
    async def _run():
        async with await NotebookLMClient.from_storage() as client:
            start_result = await client.research.start(notebook_id, topic, mode=mode)
            if not start_result:
                return {"status": "error", "report": "", "sources": [], "task_id": None}

            task_id = start_result.get("task_id")
            # Extend timeout for deep research
            timeout_secs = 180 if mode == "deep" else 60
            poll_interval = 5 if mode == "deep" else 3
            deadline = time.time() + timeout_secs

            while time.time() < deadline:
                poll = await client.research.poll(notebook_id)
                if poll.get("status") == "completed":
                    return {
                        "status": "completed",
                        "report": poll.get("report") or poll.get("summary", ""),
                        "sources": poll.get("sources", []),
                        "task_id": task_id,
                    }
                if poll.get("status") == "no_research":
                    await asyncio.sleep(poll_interval)
                    continue
                await asyncio.sleep(poll_interval)

            return {"status": "timeout", "report": "", "sources": [], "task_id": task_id}
    return asyncio.run(_run())


def import_research_sources(notebook_id: str, task_id: str, sources: list[dict]) -> list[dict]:
    """Import research sources into notebook using research.import_sources API."""
    async def _run():
        async with await NotebookLMClient.from_storage() as client:
            imported = await client.research.import_sources(notebook_id, task_id, sources)
            return imported or []
    return asyncio.run(_run())
