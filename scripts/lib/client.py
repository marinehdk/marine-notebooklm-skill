import asyncio
import time
from typing import Any

from notebooklm import NotebookLMClient
from notebooklm.exceptions import NetworkError

# Timeout for chat.ask operations (seconds).
# Notebooks with many sources can take 60+s to respond.
_ASK_TIMEOUT = 120.0

# Timeout for research source import RPC (seconds).
# The RPC may timeout while the server continues processing — we verify via sources.list().
_IMPORT_TIMEOUT = 120.0
# Timeout for waiting on each source to finish processing after import.
_IMPORT_WAIT_TIMEOUT = 120.0


def _confidence(answer: str, references: list) -> str:
    if not answer or len(answer) < 20:
        return "not_found"
    if not references:
        return "low"
    if len(references) >= 3:
        return "high"
    return "medium"


def ask(notebook_id: str, question: str, retries: int = 2, retry_delay: float = 3.0) -> dict[str, Any]:
    async def _run():
        for attempt in range(retries + 1):
            try:
                async with await NotebookLMClient.from_storage(
                    timeout=_ASK_TIMEOUT
                ) as client:
                    result = await client.chat.ask(notebook_id, question)
                    return {
                        "answer": result.answer,
                        "confidence": _confidence(result.answer, result.references),
                    }
            except NetworkError as e:
                if attempt < retries:
                    await asyncio.sleep(retry_delay)
                else:
                    raise
    return asyncio.run(_run())


async def ask_async(notebook_id: str, question: str, retries: int = 2, retry_delay: float = 3.0) -> dict[str, Any]:
    """Async version of ask() for parallel execution of Phase 1 and Phase 3.

    Returns dict with 'answer' and 'confidence' keys.
    Same retry logic and timeout handling as sync version.
    """
    for attempt in range(retries + 1):
        try:
            async with await NotebookLMClient.from_storage(
                timeout=_ASK_TIMEOUT
            ) as client:
                result = await client.chat.ask(notebook_id, question)
                return {
                    "answer": result.answer,
                    "confidence": _confidence(result.answer, result.references),
                }
        except NetworkError as e:
            if attempt < retries:
                await asyncio.sleep(retry_delay)
            else:
                raise


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
            # Real creation timestamp is at data[5][8]; data[5][5] is last-accessed.
            if len(data) > 5 and isinstance(data[5], list) and len(data[5]) > 8:
                ts = data[5][8]
                if isinstance(ts, list) and ts:
                    try:
                        real_created[nb.id] = datetime.fromtimestamp(ts[0])
                    except (TypeError, ValueError):
                        pass
            # data[1] is the sources list; library never parses this field.
            if isinstance(data[1], list):
                nb.sources_count = len(data[1])
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
            existing = await client.sources.list(notebook_id)
            normalized = url.rstrip("/").lower()
            for s in existing:
                if s.url and s.url.rstrip("/").lower() == normalized:
                    return {"skipped": True, "id": s.id, "title": s.title or url}
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


def delete_source(
    notebook_id: str,
    *,
    source_id: str | None = None,
    url: str | None = None,
) -> dict[str, Any] | None:
    """Find and delete a source by ID or URL. Returns {"id": ..., "title": ...} or None if not found."""
    async def _run():
        async with await NotebookLMClient.from_storage() as client:
            sources = await client.sources.list(notebook_id)
            if source_id:
                match = next((s for s in sources if s.id == source_id), None)
            elif url:
                normalized = url.rstrip("/").lower()
                match = next(
                    (s for s in sources if s.url and s.url.rstrip("/").lower() == normalized),
                    None,
                )
            else:
                return None
            if not match:
                return None
            await client.sources.delete(notebook_id, match.id)
            return {"id": match.id, "title": match.title}
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
            timeout_secs = 180 if mode == "deep" else 60
            poll_interval = 5 if mode == "deep" else 3
            deadline = time.time() + timeout_secs
            seen_in_progress = False

            while time.time() < deadline:
                poll = await client.research.poll(notebook_id)
                status = poll.get("status")
                if status == "in_progress":
                    seen_in_progress = True
                if status == "completed" and seen_in_progress:
                    return {
                        "status": "completed",
                        "report": poll.get("report") or poll.get("summary", ""),
                        "sources": poll.get("sources", []),
                        "task_id": task_id,
                    }
                await asyncio.sleep(poll_interval)

            return {"status": "timeout", "report": "", "sources": [], "task_id": task_id}
    return asyncio.run(_run())


async def research_async(notebook_id: str, topic: str, mode: str = "fast", retries: int = 2) -> dict[str, Any]:
    """Async version of research() for parallel execution.

    Start research and poll until complete. Returns report + sources.
    Same timeout and retry logic as sync version.

    NOTE: deep research can take 120-180s. Adjust timeout accordingly.
    fast: 60s timeout, 3s poll interval
    deep: 180s timeout, 5s poll interval
    """
    for attempt in range(retries + 1):
        try:
            async with await NotebookLMClient.from_storage() as client:
                start_result = await client.research.start(notebook_id, topic, mode=mode)
                if not start_result:
                    return {"status": "error", "report": "", "sources": [], "task_id": None}

                task_id = start_result.get("task_id")
                timeout_secs = 180 if mode == "deep" else 60
                poll_interval = 5 if mode == "deep" else 3
                deadline = time.time() + timeout_secs
                seen_in_progress = False

                while time.time() < deadline:
                    poll = await client.research.poll(notebook_id)
                    status = poll.get("status")
                    if status == "in_progress":
                        seen_in_progress = True
                    if status == "completed" and seen_in_progress:
                        return {
                            "status": "completed",
                            "report": poll.get("report") or poll.get("summary", ""),
                            "sources": poll.get("sources", []),
                            "task_id": task_id,
                        }
                    await asyncio.sleep(poll_interval)

                return {"status": "timeout", "report": "", "sources": [], "task_id": task_id}
        except NetworkError as e:
            if attempt < retries:
                await asyncio.sleep(3.0)
            else:
                raise


def import_research_sources(notebook_id: str, task_id: str, sources: list[dict]) -> list[dict]:
    """Import research sources, then wait for all to finish processing in parallel.

    Strategy:
    1. Snapshot existing source IDs before import.
    2. Fire import_sources() — RPC may timeout but server keeps processing.
    3. Poll sources.list() until new sources appear (max 15s).
    4. Use wait_for_sources() to await all new sources in parallel.
    5. Delete any that end up in ERROR state.
    6. Return only successfully imported sources.
    """
    async def _run():
        async with await NotebookLMClient.from_storage(timeout=_IMPORT_TIMEOUT) as client:
            # Step 1: snapshot existing sources
            existing = await client.sources.list(notebook_id)
            existing_ids = {s.id for s in existing}
            existing_urls = {s.url.rstrip("/").lower() for s in existing if s.url}

            # Filter out URLs already present in the notebook
            new_sources = [
                s for s in sources
                if not (s.get("url") or "").rstrip("/").lower() in existing_urls
            ]
            if not new_sources:
                return []

            # Step 2: fire import (ignore timeout — server continues processing)
            try:
                await client.research.import_sources(notebook_id, task_id, new_sources)
            except Exception:
                pass

            # Step 3: poll until new sources appear (up to 15s)
            new_sources = []
            deadline = time.time() + 15
            while time.time() < deadline:
                await asyncio.sleep(2)
                current = await client.sources.list(notebook_id)
                new_sources = [s for s in current if s.id not in existing_ids]
                if new_sources:
                    break

            if not new_sources:
                return []

            # Step 4: wait for all new sources to finish processing in parallel
            new_ids = [s.id for s in new_sources]
            try:
                finished = await client.sources.wait_for_sources(
                    notebook_id, new_ids, timeout=_IMPORT_WAIT_TIMEOUT
                )
            except Exception:
                current = await client.sources.list(notebook_id)
                finished = [s for s in current if s.id in set(new_ids)]

            # Step 5: delete failed sources
            ok, failed = [], []
            for s in finished:
                if s.is_error:
                    failed.append(s)
                    try:
                        await client.sources.delete(notebook_id, s.id)
                    except Exception:
                        pass
                else:
                    ok.append(s)

            return [{"id": s.id, "title": s.title} for s in ok]

    return asyncio.run(_run())


def deduplicate_notebook_sources(notebook_id: str) -> dict[str, int]:
    """Remove duplicate URLs from a notebook, keeping the oldest source per URL.

    Returns {"removed": N, "kept": M}.
    """
    async def _run():
        async with await NotebookLMClient.from_storage() as client:
            sources = await client.sources.list(notebook_id)

            # Group by normalized URL; sources without URL are kept as-is
            seen_urls: dict[str, str] = {}  # normalized_url -> first source id
            to_delete: list[str] = []
            for s in sources:
                if not s.url:
                    continue
                key = s.url.rstrip("/").lower()
                if key in seen_urls:
                    to_delete.append(s.id)
                else:
                    seen_urls[key] = s.id

            for source_id in to_delete:
                try:
                    await client.sources.delete(notebook_id, source_id)
                except Exception:
                    pass

            return {"removed": len(to_delete), "kept": len(sources) - len(to_delete)}

    return asyncio.run(_run())


def get_notebook_descriptions(notebook_ids: list[str]) -> dict[str, dict]:
    """Fetch AI-generated summary and suggested topics for a list of notebooks.

    Returns a dict keyed by notebook ID:
      {"summary": str (≤300 chars), "topics": list[str] (≤5 items)}
    Failed fetches return {"summary": "", "topics": []}.
    """
    async def _fetch_one(client, nb_id: str) -> tuple[str, dict]:
        try:
            desc = await client.notebooks.get_description(nb_id)
            summary = (desc.summary or "")[:300]
            topics = [t.question for t in (desc.suggested_topics or [])[:5]]
            return nb_id, {"summary": summary, "topics": topics}
        except Exception:
            return nb_id, {"summary": "", "topics": []}

    async def _run():
        async with await NotebookLMClient.from_storage() as client:
            results = await asyncio.gather(
                *[_fetch_one(client, nb_id) for nb_id in notebook_ids]
            )
            return dict(results)

    return asyncio.run(_run())
