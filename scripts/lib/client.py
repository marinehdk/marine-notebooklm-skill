import asyncio
import time
from typing import Any

from notebooklm import NotebookLMClient
from notebooklm.exceptions import NetworkError


class CapacityError(Exception):
    """Raised when a notebook is at or near its source capacity limit."""

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

    NOTE: deep research can take 3-10 mins. Adjust timeout accordingly.
    fast: 60s timeout, 3s poll interval
    deep: 600s timeout, 10s poll interval
    """
    async def _run():
        async with await NotebookLMClient.from_storage() as client:
            start_result = await client.research.start(notebook_id, topic, mode=mode)
            if not start_result:
                return {"status": "error", "report": "", "sources": [], "task_id": None}

            task_id = start_result.get("task_id")
            timeout_secs = 600 if mode == "deep" else 60
            poll_interval = 10 if mode == "deep" else 1
            # Grace period = 3 poll cycles. Accepts "completed" without seen_in_progress
            # only after this window, to guard against picking up a stale result from a
            # previous research while the new task hasn't registered yet.
            grace_secs = poll_interval * 3
            deadline = time.time() + timeout_secs
            loop_start = time.time()
            seen_in_progress = False

            while time.time() < deadline:
                poll = await client.research.poll(notebook_id)
                status = poll.get("status")
                if status == "in_progress":
                    seen_in_progress = True
                if status == "completed" and (seen_in_progress or time.time() - loop_start > grace_secs):
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

    NOTE: deep research can take 3-10 mins. Adjust timeout accordingly.
    fast: 60s timeout, 3s poll interval
    deep: 600s timeout, 10s poll interval
    """
    for attempt in range(retries + 1):
        try:
            async with await NotebookLMClient.from_storage() as client:
                start_result = await client.research.start(notebook_id, topic, mode=mode)
                if not start_result:
                    return {"status": "error", "report": "", "sources": [], "task_id": None}

                task_id = start_result.get("task_id")
                timeout_secs = 600 if mode == "deep" else 60
                poll_interval = 10 if mode == "deep" else 1
                grace_secs = poll_interval * 3
                deadline = time.time() + timeout_secs
                loop_start = time.time()
                seen_in_progress = False

                while time.time() < deadline:
                    poll = await client.research.poll(notebook_id)
                    status = poll.get("status")
                    if status == "in_progress":
                        seen_in_progress = True
                    if status == "completed" and (seen_in_progress or time.time() - loop_start > grace_secs):
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


_NOTEBOOK_CAPACITY = 300
_NOTEBOOK_CAPACITY_WARN = 290  # warn and cap imports at this threshold


def import_research_sources(
    notebook_id: str,
    task_id: str,
    sources: list[dict],
    max_sources: int | None = None,
) -> list[dict]:
    """Import research sources, then wait for all to finish processing in parallel.

    Strategy:
    1. Snapshot existing source IDs before import.
    2. Guard against notebook capacity (300 source limit); trim to max_sources if set.
    3. Fire import_sources() — RPC may timeout but server keeps processing.
    4. Poll sources.list() until new sources appear (30s normal, 45s if import RPC timed out).
    5. Use wait_for_sources() to await all new sources in parallel.
    6. Delete any that end up in ERROR state.
    7. Return only successfully imported sources.
    """
    async def _run():
        async with await NotebookLMClient.from_storage(timeout=_IMPORT_TIMEOUT) as client:
            # Step 1: snapshot existing sources
            existing = await client.sources.list(notebook_id)
            existing_ids = {s.id for s in existing}
            existing_urls = {s.url.rstrip("/").lower() for s in existing if s.url}

            # Step 2a: capacity guard — refuse to import when at or near limit
            available_slots = _NOTEBOOK_CAPACITY_WARN - len(existing)
            if available_slots <= 0:
                raise CapacityError(
                    f"Notebook is at capacity ({len(existing)}/{_NOTEBOOK_CAPACITY} sources). "
                    "Run /nlm-deduplicate to free space before importing more sources."
                )

            # Step 2b: filter already-present URLs, then apply max_sources and capacity caps
            new_sources = [
                s for s in sources
                if not (s.get("url") or "").rstrip("/").lower() in existing_urls
            ]
            cap = min(available_slots, max_sources if max_sources is not None else len(new_sources))
            new_sources = new_sources[:cap]

            if not new_sources:
                return []

            # Step 3: fire import (RPC may timeout — server keeps processing regardless)
            import_ok = False
            try:
                await client.research.import_sources(notebook_id, task_id, new_sources)
                import_ok = True
            except Exception:
                pass

            # Step 3: poll until new sources appear (up to 45s; longer window for deep
            # research with many sources, or when the import RPC timed out server-side)
            new_sources = []
            detect_deadline = time.time() + (45 if not import_ok else 30)
            while time.time() < detect_deadline:
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
    """Remove duplicate URLs and failed sources from a notebook.

    Keeps the oldest source per URL; deletes all is_error sources.
    Returns {"removed": N, "failed_removed": F, "kept": M}.
    """
    async def _run():
        async with await NotebookLMClient.from_storage() as client:
            sources = await client.sources.list(notebook_id)

            to_delete: list[str] = []

            # Delete failed sources first
            failed_ids: set[str] = set()
            for s in sources:
                if getattr(s, "is_error", False):
                    failed_ids.add(s.id)
                    to_delete.append(s.id)

            # Group non-failed sources by normalized URL; keep oldest, delete duplicates
            seen_urls: dict[str, str] = {}  # normalized_url -> first source id
            dup_ids: list[str] = []
            for s in sources:
                if s.id in failed_ids or not s.url:
                    continue
                key = s.url.rstrip("/").lower()
                if key in seen_urls:
                    dup_ids.append(s.id)
                    to_delete.append(s.id)
                else:
                    seen_urls[key] = s.id

            for source_id in to_delete:
                try:
                    await client.sources.delete(notebook_id, source_id)
                except Exception:
                    pass

            kept = len(sources) - len(to_delete)
            return {"removed": len(dup_ids), "failed_removed": len(failed_ids), "kept": kept}

    return asyncio.run(_run())


def _score_keywords(source_keywords: list[str], topic_weights: dict[str, float]) -> float:
    """Score source keywords against a topic weight profile. Returns 0.0–1.0.

    Uses bidirectional substring matching so "COLREGs 避碰" hits topic "避碰"
    and vice versa.  Returns 0.5 when topic_weights or source_keywords is empty
    (neutral/no-op — prevents new sources with no keywords from being auto-deleted).
    """
    if not topic_weights:
        return 0.5
    if not source_keywords:  # GAP-1: fallback keep for sources with empty keywords
        return 0.5
    total = sum(topic_weights.values())
    if total == 0.0:
        return 0.5
    source_lower = [k.lower() for k in source_keywords if k]
    if not source_lower:  # GAP-1: all entries were empty strings
        return 0.5
    matched = 0.0
    for tw, w in topic_weights.items():
        tw_lower = tw.lower()
        for sk in source_lower:
            if tw_lower in sk or sk in tw_lower:
                matched += w
                break
    return min(1.0, matched / total)


def score_and_prune_sources(
    notebook_id: str,
    source_ids: list[str],
    topic_weights: dict[str, float],
    min_score: float = 0.1,
) -> dict:
    """Score newly imported sources via get_guide() (advisory only; no deletion).

    Args:
        notebook_id:   Target notebook.
        source_ids:    IDs of sources to evaluate (typically freshly imported).
        topic_weights: Keyword→weight profile from TopicTracker.keyword_weights().
                       Pass {} to skip scoring entirely (all sources kept).
        min_score:     (reserved, no longer used for deletion; scores are advisory)

    Returns dict with keys:
        scored         – list of {id, keywords, summary, score, kept}
        kept           – count of sources kept (always == len(source_ids))
        pruned         – always 0 (spec §3.3.5: no auto-delete)
        notebook_count – same as kept; for caller use
    """
    async def _guide_one(client, sid: str) -> tuple[str, dict | Exception]:
        try:
            return sid, await client.sources.get_guide(notebook_id, sid)
        except Exception as e:
            return sid, e

    async def _run():
        async with await NotebookLMClient.from_storage() as client:
            # Fetch all guides in parallel
            pairs = await asyncio.gather(*[_guide_one(client, sid) for sid in source_ids])

            scored = []

            for sid, guide in pairs:
                if isinstance(guide, Exception):
                    # Can't score → keep by default
                    scored.append({"id": sid, "score": None, "kept": True,
                                   "error": type(guide).__name__})
                    continue

                keywords = guide.get("keywords", [])
                score = _score_keywords(keywords, topic_weights)
                scored.append({
                    "id": sid,
                    "keywords": keywords,
                    "summary": (guide.get("summary") or "")[:120],
                    "score": round(score, 3),
                    "kept": True,  # GAP-1/spec §3.3.5: never auto-delete; advisory only
                })

            # GAP-4: notebook_count field; GAP-1: no deletion
            return {
                "scored": scored,
                "kept": len(scored),
                "pruned": 0,
                "notebook_count": len(scored),
            }

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
