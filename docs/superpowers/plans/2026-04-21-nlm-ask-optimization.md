# nlm-ask Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Claude-Haiku-based notebook routing and low-confidence handling to `nlm ask`, backed by AI-generated description metadata cached alongside the notebook list.

**Architecture:** A new `notebook_router.py` sends question + notebook summaries/topics to Claude Haiku to pick the most relevant notebooks; a new `confidence_handler.py` attaches a `next_action` hint or auto-triggers fast research when confidence is low. Both are wired into `cmd_ask` via a new `--on-low-confidence` flag.

**Tech Stack:** Python 3.12+, `anthropic` SDK (new dep), `notebooklm-py` (`client.notebooks.get_description`), `asyncio.gather` for parallel description fetching.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `requirements.txt` | Modify | Add `anthropic` dependency |
| `scripts/lib/client.py` | Modify | Add `get_notebook_descriptions(ids)` — parallel async fetch |
| `scripts/nlm.py` → `cmd_setup` | Modify | Call `get_notebook_descriptions` during `--notebook-list`, write to cache |
| `scripts/lib/notebook_router.py` | Create | Claude Haiku routing + keyword fallback |
| `scripts/lib/confidence_handler.py` | Create | `prompt` / `research` / `silent` modes |
| `scripts/nlm.py` → `cmd_ask` | Modify | Wire router + handler; add `--on-low-confidence` param |
| `skills/nlm-ask/SKILL.md` | Modify | Add auto-trigger rules, result handling table, new param |
| `tests/test_router.py` | Create | Unit tests for router |
| `tests/test_confidence.py` | Create | Unit tests for confidence handler |

---

## Task 1: Add `anthropic` to requirements

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add dependency**

```
git+https://github.com/teng-lin/notebooklm-py.git
anthropic>=0.40.0
```

- [ ] **Step 2: Install in the deployed venv**

```bash
~/.claude/skills/nlm/.venv/bin/pip install "anthropic>=0.40.0"
```

Expected: `Successfully installed anthropic-...`

- [ ] **Step 3: Verify import**

```bash
~/.claude/skills/nlm/.venv/bin/python3 -c "import anthropic; print(anthropic.__version__)"
```

Expected: version string, no error.

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "chore: add anthropic SDK dependency for notebook router"
```

---

## Task 2: Add `get_notebook_descriptions()` to `client.py`

**Files:**
- Modify: `scripts/lib/client.py`

Cache format stores notebooks with lowercase keys (`id`, `title`, `source_count`, `description`, `created_at`). We add `summary` and `topics` to each entry.

- [ ] **Step 1: Write the failing test**

Create `tests/test_client_descriptions.py`:

```python
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib.client import get_notebook_descriptions


def test_get_notebook_descriptions_returns_dict():
    mock_desc = MagicMock()
    mock_desc.summary = "This notebook covers UKC calculations."
    mock_desc.suggested_topics = [
        MagicMock(question="How is squat calculated?"),
        MagicMock(question="What margins apply in shallow water?"),
    ]

    mock_notebooks_api = AsyncMock()
    mock_notebooks_api.get_description = AsyncMock(return_value=mock_desc)

    mock_client = AsyncMock()
    mock_client.notebooks = mock_notebooks_api
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("lib.client.NotebookLMClient") as MockClient:
        MockClient.from_storage = AsyncMock(return_value=mock_client)
        result = get_notebook_descriptions(["abc-123"])

    assert "abc-123" in result
    assert result["abc-123"]["summary"] == "This notebook covers UKC calculations."
    assert result["abc-123"]["topics"] == [
        "How is squat calculated?",
        "What margins apply in shallow water?",
    ]


def test_get_notebook_descriptions_handles_failure():
    mock_notebooks_api = AsyncMock()
    mock_notebooks_api.get_description = AsyncMock(side_effect=Exception("RPC failed"))

    mock_client = AsyncMock()
    mock_client.notebooks = mock_notebooks_api
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("lib.client.NotebookLMClient") as MockClient:
        MockClient.from_storage = AsyncMock(return_value=mock_client)
        result = get_notebook_descriptions(["bad-id"])

    assert result["bad-id"] == {"summary": "", "topics": []}


def test_get_notebook_descriptions_truncates_summary():
    long_summary = "x" * 500
    mock_desc = MagicMock()
    mock_desc.summary = long_summary
    mock_desc.suggested_topics = []

    mock_notebooks_api = AsyncMock()
    mock_notebooks_api.get_description = AsyncMock(return_value=mock_desc)

    mock_client = AsyncMock()
    mock_client.notebooks = mock_notebooks_api
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("lib.client.NotebookLMClient") as MockClient:
        MockClient.from_storage = AsyncMock(return_value=mock_client)
        result = get_notebook_descriptions(["nb1"])

    assert len(result["nb1"]["summary"]) == 300
```

- [ ] **Step 2: Run to verify failure**

```bash
cd /Users/marine/Code/NotebookLM\ SKILL/marine-notebooklm-skill
~/.claude/skills/nlm/.venv/bin/python -m pytest tests/test_client_descriptions.py -v 2>&1 | head -30
```

Expected: `ImportError` or `AttributeError` — `get_notebook_descriptions` doesn't exist yet.

- [ ] **Step 3: Implement `get_notebook_descriptions` in `client.py`**

Add after the existing `list_notebooks()` function:

```python
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
```

- [ ] **Step 4: Run tests to verify pass**

```bash
~/.claude/skills/nlm/.venv/bin/python -m pytest tests/test_client_descriptions.py -v
```

Expected: 3 PASSED.

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/client.py tests/test_client_descriptions.py
git commit -m "feat(client): add get_notebook_descriptions() parallel fetch"
```

---

## Task 3: Enrich notebook cache with descriptions during refresh

**Files:**
- Modify: `scripts/nlm.py` (inside `cmd_setup`, the `--notebook-list` branch)

The cache is written by `save_notebooks_cache(project_path, notebooks)` where `notebooks` is a list of dicts with keys `id`, `title`, `source_count`, `description`, `created_at`. We add `summary` and `topics` to each dict before saving.

- [ ] **Step 1: Find the `--notebook-list` branch in `cmd_setup`**

```bash
grep -n "notebook.list\|notebook_list\|save_notebooks_cache\|list_notebooks" \
  /Users/marine/Code/NotebookLM\ SKILL/marine-notebooklm-skill/scripts/nlm.py
```

Note the line numbers. The branch starts after `assert_authenticated()` and calls `client.list_notebooks()`, then `save_notebooks_cache`.

- [ ] **Step 2: Add description enrichment after `list_notebooks()` call**

Locate the block that calls `client.list_notebooks()` and `save_notebooks_cache()`. Modify it to:

```python
# ── Notebook list (with cache) ────────────────────────────────────────────
if parsed.notebook_list:
    force_refresh = parsed.refresh
    cached = None if force_refresh else load_notebooks_cache(project_path)
    if cached is not None:
        notebooks = cached["notebooks"]
    else:
        notebooks = client.list_notebooks()
        # Enrich with AI descriptions (parallel fetch)
        nb_ids = [nb["id"] for nb in notebooks]
        descriptions = client.get_notebook_descriptions(nb_ids)
        for nb in notebooks:
            desc = descriptions.get(nb["id"], {"summary": "", "topics": []})
            nb["summary"] = desc["summary"]
            nb["topics"] = desc["topics"]
        save_notebooks_cache(project_path, notebooks)

    # Build display table
    table = [
        {
            "#": i + 1,
            "UUID": nb["id"],
            "Title": nb["title"],
            "Sources": nb.get("source_count", 0),
            "Description": nb.get("description", ""),
            "Created": str(nb.get("created_at", ""))[:10],
        }
        for i, nb in enumerate(notebooks)
    ]
    print(json.dumps({
        "action": "select_notebook",
        "cache": {
            "cached": cached is not None,
            "cached_at": ...,   # preserve existing cache metadata logic
            "ttl_hours": 24,
        },
        "total": len(table),
        "table": table,
        "next_step": {
            "hint": "选择一个作为本项目的 Local 笔记本，或新建一个",
            "commands": [
                "nlm setup --add-local-notebook <UUID>",
                "nlm setup --create-local \"<新笔记本名称>\"",
            ],
        },
    }, indent=2, ensure_ascii=False))
    return
```

**Important:** Read the existing `--notebook-list` block carefully before editing. Preserve the `cached_at` and `cache` metadata output logic exactly. Only add the description enrichment call after `client.list_notebooks()`.

- [ ] **Step 3: Verify manually**

```bash
bash ~/.claude/skills/nlm/scripts/invoke.sh setup --notebook-list --refresh 2>&1 | python3 -m json.tool | grep -A5 '"UUID": "b6f5c3bb'
```

Expected: The UKC notebook entry includes `"summary"` and `"topics"` fields in cache. Check `.nlm/notebooks_cache.json`:

```bash
python3 -m json.tool /path/to/project/.nlm/notebooks_cache.json | grep -A8 '"summary"' | head -20
```

- [ ] **Step 4: Commit**

```bash
git add scripts/nlm.py
git commit -m "feat(setup): enrich notebook cache with AI descriptions on refresh"
```

---

## Task 4: Build `notebook_router.py`

**Files:**
- Create: `scripts/lib/notebook_router.py`
- Create: `tests/test_router.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_router.py`:

```python
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib.notebook_router import route_notebooks, RouteResult, _keyword_rank

NOTEBOOKS = [
    {
        "id": "ukc-uuid",
        "title": "SINAN-业务子系统层UKC设计",
        "summary": "本笔记本涵盖船舶UKC龙骨下余量计算。",
        "topics": ["How is squat calculated?", "What margins apply?"],
    },
    {
        "id": "colav-uuid",
        "title": "SINAN-业务子系统层COLAV设计",
        "summary": "本笔记本涵盖碰撞规避算法。",
        "topics": ["How does COLAV work?", "What is DCPA?"],
    },
    {
        "id": "general-uuid",
        "title": "航线设计研究",
        "summary": "航线规划方法综述。",
        "topics": ["How to plan a voyage?"],
    },
]


def test_keyword_rank_matches_title():
    ranked = _keyword_rank("UKC squat calculation", NOTEBOOKS)
    assert ranked[0] == "ukc-uuid"


def test_keyword_rank_zero_hits_returns_first_three():
    ranked = _keyword_rank("quantum entanglement", NOTEBOOKS)
    assert len(ranked) == 3
    assert ranked == ["ukc-uuid", "colav-uuid", "general-uuid"]


def test_keyword_rank_respects_limit():
    many = NOTEBOOKS * 5
    ranked = _keyword_rank("UKC", many)
    assert len(ranked) <= 3


def test_route_notebooks_uses_claude_result():
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='["colav-uuid", "ukc-uuid"]')]

    with patch("lib.notebook_router.anthropic.Anthropic") as MockAnthropicClass:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        MockAnthropicClass.return_value = mock_client

        result = route_notebooks("collision avoidance DCPA", NOTEBOOKS)

    assert result.fallback_used is False
    assert result.ranked_ids == ["colav-uuid", "ukc-uuid"]


def test_route_notebooks_falls_back_on_api_error():
    with patch("lib.notebook_router.anthropic.Anthropic") as MockAnthropicClass:
        MockAnthropicClass.return_value.messages.create.side_effect = Exception("no key")
        result = route_notebooks("UKC squat", NOTEBOOKS)

    assert result.fallback_used is True
    assert result.ranked_ids[0] == "ukc-uuid"


def test_route_notebooks_filters_invalid_uuids():
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='["nonexistent-uuid", "ukc-uuid"]')]

    with patch("lib.notebook_router.anthropic.Anthropic") as MockAnthropicClass:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        MockAnthropicClass.return_value = mock_client

        result = route_notebooks("UKC", NOTEBOOKS)

    assert "nonexistent-uuid" not in result.ranked_ids
    assert "ukc-uuid" in result.ranked_ids


def test_route_notebooks_empty_list():
    result = route_notebooks("anything", [])
    assert result.ranked_ids == []
    assert result.fallback_used is False
```

- [ ] **Step 2: Run to verify failure**

```bash
~/.claude/skills/nlm/.venv/bin/python -m pytest tests/test_router.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'lib.notebook_router'`

- [ ] **Step 3: Implement `notebook_router.py`**

Create `scripts/lib/notebook_router.py`:

```python
"""Route questions to the most relevant notebooks via Claude Haiku.

Falls back to title keyword matching if the API call fails.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import anthropic


_STOP_WORDS = frozenset(
    "the a an is in of to and for how what does did does can could would should".split()
)

_ROUTER_MODEL = "claude-haiku-4-5-20251001"


@dataclass
class RouteResult:
    ranked_ids: list[str] = field(default_factory=list)
    fallback_used: bool = False


def route_notebooks(question: str, notebooks: list[dict], scope: str = "auto") -> RouteResult:
    """Return notebooks ranked by relevance to question.

    Args:
        question: The user's question text.
        notebooks: List of notebook dicts with keys: id, title, summary, topics.
        scope: Informational only — caller is responsible for passing the right pool.

    Returns:
        RouteResult with ranked_ids (≤3) and fallback_used flag.
    """
    if not notebooks:
        return RouteResult()

    try:
        ranked = _claude_route(question, notebooks)
        valid_ids = {nb["id"] for nb in notebooks}
        ranked = [uid for uid in ranked if uid in valid_ids][:3]
        return RouteResult(ranked_ids=ranked, fallback_used=False)
    except Exception:
        return RouteResult(ranked_ids=_keyword_rank(question, notebooks), fallback_used=True)


def _claude_route(question: str, notebooks: list[dict]) -> list[str]:
    """Ask Claude Haiku to rank notebooks by relevance. Returns UUID list."""
    lines = []
    for i, nb in enumerate(notebooks, 1):
        summary = (nb.get("summary") or "")[:200]
        topics = " / ".join((nb.get("topics") or [])[:3])
        lines.append(
            f'[{i}] UUID: {nb["id"]} | Title: {nb["title"]}\n'
            f'    Summary: {summary}\n'
            f'    Topics: {topics}'
        )

    prompt = (
        "You are a notebook router. Given a question and a list of notebooks, "
        "return the UUIDs of the most relevant notebooks in order of relevance.\n\n"
        f"Question: {question}\n\n"
        "Notebooks:\n" + "\n\n".join(lines) + "\n\n"
        "Reply with ONLY a JSON array of UUIDs, most relevant first. Include at most 3.\n"
        'Example: ["uuid-1", "uuid-2"]'
    )

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=_ROUTER_MODEL,
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}],
    )
    return json.loads(response.content[0].text.strip())


def _keyword_rank(question: str, notebooks: list[dict]) -> list[str]:
    """Rank notebooks by title keyword overlap with question."""
    tokens = {
        t.lower()
        for t in re.split(r"[\s\W]+", question)
        if t and t.lower() not in _STOP_WORDS
    }
    scores: list[tuple[int, str]] = []
    for nb in notebooks:
        title_lower = nb["title"].lower()
        score = sum(1 for t in tokens if t in title_lower)
        scores.append((score, nb["id"]))
    scores.sort(reverse=True)
    return [uid for _, uid in scores[:3]]
```

- [ ] **Step 4: Run tests**

```bash
~/.claude/skills/nlm/.venv/bin/python -m pytest tests/test_router.py -v
```

Expected: 7 PASSED.

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/notebook_router.py tests/test_router.py
git commit -m "feat(router): add Claude Haiku notebook router with keyword fallback"
```

---

## Task 5: Build `confidence_handler.py`

**Files:**
- Create: `scripts/lib/confidence_handler.py`
- Create: `tests/test_confidence.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_confidence.py`:

```python
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib.confidence_handler import handle_confidence

_HIGH = {"answer": "Answer.", "confidence": "high", "citations": [], "source_notebook": "local"}
_LOW  = {"answer": "Partial.", "confidence": "low",  "citations": [], "source_notebook": "local"}
_NONE = {"answer": "",        "confidence": "not_found", "citations": [], "source_notebook": "local"}


def test_silent_mode_returns_unchanged():
    result = handle_confidence(_HIGH.copy(), mode="silent", local_nb_id="nb1", question="Q")
    assert "next_action" not in result
    assert result["confidence"] == "high"


def test_silent_mode_on_low_returns_unchanged():
    result = handle_confidence(_LOW.copy(), mode="silent", local_nb_id="nb1", question="Q")
    assert "next_action" not in result


def test_prompt_mode_high_confidence_unchanged():
    result = handle_confidence(_HIGH.copy(), mode="prompt", local_nb_id="nb1", question="Q")
    assert "next_action" not in result


def test_prompt_mode_low_adds_next_action():
    result = handle_confidence(_LOW.copy(), mode="prompt", local_nb_id="nb1", question="Q")
    assert "next_action" in result
    assert result["next_action"]["type"] == "suggest_research"
    assert "nlm research" in result["next_action"]["command"]
    assert "Q" in result["next_action"]["command"]


def test_prompt_mode_not_found_adds_next_action():
    result = handle_confidence(_NONE.copy(), mode="prompt", local_nb_id="nb1", question="Q")
    assert result["next_action"]["type"] == "suggest_research"


def test_research_mode_retries_on_success():
    research_result = {
        "status": "completed",
        "task_id": "task-1",
        "sources": [{"url": "http://example.com"}],
    }
    retry_result = {"answer": "Better answer.", "confidence": "high", "citations": []}

    with patch("lib.confidence_handler.nlm_client") as mock_client:
        mock_client.research.return_value = research_result
        mock_client.import_research_sources.return_value = []
        mock_client.ask.return_value = retry_result

        result = handle_confidence(_LOW.copy(), mode="research", local_nb_id="nb1", question="Q")

    assert result["confidence"] == "high"
    assert result["auto_researched"] is True
    assert "next_action" not in result


def test_research_mode_degrades_to_prompt_if_still_low():
    research_result = {"status": "completed", "task_id": "t1", "sources": []}
    still_low = {"answer": "Still partial.", "confidence": "low", "citations": []}

    with patch("lib.confidence_handler.nlm_client") as mock_client:
        mock_client.research.return_value = research_result
        mock_client.import_research_sources.return_value = []
        mock_client.ask.return_value = still_low

        result = handle_confidence(_LOW.copy(), mode="research", local_nb_id="nb1", question="Q")

    assert result["auto_researched"] is True
    assert "next_action" in result
    assert result["next_action"]["type"] == "suggest_research"


def test_research_mode_without_local_nb_falls_back_to_prompt():
    result = handle_confidence(_LOW.copy(), mode="research", local_nb_id=None, question="Q")
    assert "next_action" in result
    assert "auto_researched" not in result
```

- [ ] **Step 2: Run to verify failure**

```bash
~/.claude/skills/nlm/.venv/bin/python -m pytest tests/test_confidence.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'lib.confidence_handler'`

- [ ] **Step 3: Implement `confidence_handler.py`**

Create `scripts/lib/confidence_handler.py`:

```python
"""Handle low-confidence ask results: prompt, research, or silent."""
from __future__ import annotations

from typing import Any

from lib import client as nlm_client  # imported as module so tests can patch it


_LOW_CONFIDENCE = frozenset({"low", "not_found"})


def handle_confidence(
    result: dict[str, Any],
    mode: str,
    local_nb_id: str | None,
    question: str,
) -> dict[str, Any]:
    """Apply post-processing based on confidence level and mode.

    Args:
        result:      Output dict from client.ask().
        mode:        "prompt" | "research" | "silent"
        local_nb_id: Local notebook ID (required for research mode).
        question:    Original question text (used in next_action command).

    Returns:
        Possibly modified result dict.
    """
    confidence = result.get("confidence", "not_found")

    if confidence not in _LOW_CONFIDENCE or mode == "silent":
        return result

    if mode == "research" and local_nb_id:
        return _research_and_retry(result, local_nb_id, question)

    return _attach_prompt_hint(result, question)


def _attach_prompt_hint(result: dict[str, Any], question: str) -> dict[str, Any]:
    result["next_action"] = {
        "type": "suggest_research",
        "message": (
            "本地笔记本对此问题置信度较低，建议通过 `/nlm-research` 补充相关资料后重试。"
        ),
        "command": f'nlm research --topic "{question}" --add-sources --project-path "."',
    }
    return result


def _research_and_retry(
    original: dict[str, Any],
    local_nb_id: str,
    question: str,
) -> dict[str, Any]:
    research = nlm_client.research(local_nb_id, question, mode="fast")

    if research.get("status") == "completed" and research.get("sources"):
        nlm_client.import_research_sources(
            local_nb_id,
            research["task_id"],
            research["sources"],
        )

    retry = nlm_client.ask(local_nb_id, question)
    retry["auto_researched"] = True
    retry["source_notebook"] = original.get("source_notebook", "local")

    if retry.get("confidence") in _LOW_CONFIDENCE:
        return _attach_prompt_hint(retry, question)

    return retry
```

- [ ] **Step 4: Run tests**

```bash
~/.claude/skills/nlm/.venv/bin/python -m pytest tests/test_confidence.py -v
```

Expected: 8 PASSED.

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/confidence_handler.py tests/test_confidence.py
git commit -m "feat(confidence): add prompt/research/silent low-confidence handler"
```

---

## Task 6: Wire router and handler into `cmd_ask`

**Files:**
- Modify: `scripts/nlm.py` → `cmd_ask` function (lines ~274-323)

The new `cmd_ask` replaces the current `find_notebook_ids` + sequential-query loop with:
1. Config + cache load → build `{id: notebook_metadata}` lookup
2. Scope-based candidate selection
3. Router call (for global or auto-global phase)
4. Sequential query until high/medium confidence
5. Confidence handler

- [ ] **Step 1: Add imports at top of `nlm.py`**

Find the import block near the top of `scripts/nlm.py` and add:

```python
from lib.notebook_router import route_notebooks
from lib.confidence_handler import handle_confidence
```

- [ ] **Step 2: Replace `cmd_ask` function entirely**

The complete new `cmd_ask` (replace lines from `def cmd_ask` to the next `def cmd_`):

```python
def cmd_ask(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="nlm ask")
    parser.add_argument("--question", required=True)
    parser.add_argument("--scope", choices=["auto", "local", "global"], default="auto")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    parser.add_argument("--project-path", default=".")
    parser.add_argument(
        "--on-low-confidence",
        choices=["prompt", "research", "silent"],
        default="prompt",
    )
    parsed = parser.parse_args(args)

    assert_authenticated()
    project_path = Path(parsed.project_path).expanduser().resolve()

    config = load_project_config(project_path)
    local_nb_id = _resolve_local_id(config)
    global_nb_ids = _resolve_global_ids(config)

    if not local_nb_id and not global_nb_ids:
        print(json.dumps({"error": "No notebooks configured. Run: nlm setup"}))
        sys.exit(1)

    # Build lookup from cache for router metadata
    cache = load_notebooks_cache(project_path)
    cache_by_id: dict[str, dict] = {}
    if cache:
        for nb in cache.get("notebooks", []):
            cache_by_id[nb["id"]] = nb

    result = None
    source_notebook = "unknown"

    if parsed.scope == "local":
        if not local_nb_id:
            print(json.dumps({"error": "No local notebook configured. Run: nlm setup"}))
            sys.exit(1)
        result = client.ask(local_nb_id, parsed.question)
        source_notebook = "local"

    elif parsed.scope == "global":
        if not global_nb_ids:
            print(json.dumps({"error": "No global notebooks configured. Run: nlm setup --add-global-notebook UUID"}))
            sys.exit(1)
        global_pool = [cache_by_id[uid] for uid in global_nb_ids if uid in cache_by_id]
        if global_pool and any(nb.get("summary") for nb in global_pool):
            route = route_notebooks(parsed.question, global_pool)
            ranked = route.ranked_ids or global_nb_ids[:3]
        else:
            ranked = global_nb_ids[:3]
        for nb_id in ranked:
            r = client.ask(nb_id, parsed.question)
            if r["confidence"] not in ("low", "not_found"):
                result = r
                source_notebook = "global"
                break
            result = r
            source_notebook = "global"

    else:  # auto
        # Phase 1: try local notebook
        if local_nb_id:
            result = client.ask(local_nb_id, parsed.question)
            source_notebook = "local"

        # Phase 2: if no local or low confidence, route among globals
        if (result is None or result.get("confidence") in ("low", "not_found")) and global_nb_ids:
            global_pool = [cache_by_id[uid] for uid in global_nb_ids if uid in cache_by_id]
            if global_pool and any(nb.get("summary") for nb in global_pool):
                route = route_notebooks(parsed.question, global_pool)
                ranked = route.ranked_ids or global_nb_ids[:3]
            else:
                ranked = global_nb_ids[:3]
            for nb_id in ranked:
                if nb_id == local_nb_id:
                    continue
                r = client.ask(nb_id, parsed.question)
                if r["confidence"] not in ("low", "not_found"):
                    result = r
                    source_notebook = "global"
                    break
                result = r
                source_notebook = "global"

    if result is None:
        print(json.dumps({"error": "No notebooks available to query"}))
        sys.exit(1)

    result["source_notebook"] = source_notebook

    result = handle_confidence(
        result,
        mode=parsed.on_low_confidence,
        local_nb_id=local_nb_id,
        question=parsed.question,
    )

    if parsed.format == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"\n📝 Answer:\n{result['answer']}\n")
        print(f"🎯 Confidence: {result['confidence']} (from {source_notebook} notebook)")
        if result.get("citations"):
            print(f"📚 {len(result['citations'])} citation(s)")
        if result.get("next_action"):
            print(f"\n💡 {result['next_action']['message']}")
```

**Note:** `_resolve_local_id` and `_resolve_global_ids` are already imported from `lib.registry` — verify they are in the import block at the top of `nlm.py`. If not, add them.

- [ ] **Step 3: Verify imports are complete**

```bash
grep "from lib.registry import\|from lib.notebook_router\|from lib.confidence_handler" \
  /Users/marine/Code/NotebookLM\ SKILL/marine-notebooklm-skill/scripts/nlm.py
```

Expected output shows all three imports. If `_resolve_local_id` / `_resolve_global_ids` are missing from the registry import, add them.

- [ ] **Step 4: Smoke test with real auth**

```bash
bash ~/.claude/skills/nlm/scripts/invoke.sh ask \
  --question "What is the UKC safety margin for restricted waters?" \
  --project-path "." \
  --format json 2>&1 | python3 -m json.tool
```

Expected: JSON with `answer`, `confidence`, `source_notebook`, and optionally `next_action`.

- [ ] **Step 5: Test `--scope global` routing**

```bash
bash ~/.claude/skills/nlm/scripts/invoke.sh ask \
  --question "COLAV DCPA threshold" \
  --scope global \
  --project-path "." \
  --format json 2>&1 | python3 -m json.tool
```

Expected: response from a COLAV-related global notebook (check `source_notebook` field).

- [ ] **Step 6: Test `--on-low-confidence silent`**

```bash
bash ~/.claude/skills/nlm/scripts/invoke.sh ask \
  --question "quantum entanglement in marine propulsion" \
  --on-low-confidence silent \
  --project-path "." \
  --format json 2>&1 | python3 -m json.tool
```

Expected: `confidence: "not_found"` or `"low"`, no `next_action` field.

- [ ] **Step 7: Commit**

```bash
git add scripts/nlm.py
git commit -m "feat(ask): wire notebook router and confidence handler into cmd_ask"
```

---

## Task 7: Update `skills/nlm-ask/SKILL.md`

**Files:**
- Modify: `skills/nlm-ask/SKILL.md`

- [ ] **Step 1: Replace the file contents**

```markdown
---
name: nlm-ask
description: Query NotebookLM notebooks. Use when user asks about concepts, APIs, architecture patterns, or domain knowledge that might be in their curated notebook sources.
allowed-tools:
  - Bash
---

# nlm-ask

Query your NotebookLM notebook for grounded answers. Auto-triggered when Claude encounters knowledge uncertainty.

## Parameters

| Parameter | Values | Default | Description |
|-----------|--------|---------|-------------|
| `--question` | text | required | The question to ask |
| `--scope` | `auto\|local\|global` | `auto` | `auto` = local first, then route among globals; `local` = project notebook only; `global` = route among global notebooks |
| `--on-low-confidence` | `prompt\|research\|silent` | `prompt` | `prompt` = attach hint; `research` = auto fast-research then retry; `silent` = return as-is |
| `--format` | `json\|text` | `json` | Output format |
| `--project-path` | path | `$(pwd)` | Project root containing `.nlm/config.json` |

## Usage

```bash
INVOKE="bash $HOME/.claude/skills/nlm/scripts/invoke.sh"
$INVOKE ask --question "<question>" --scope auto --format json
```

## Output

```json
{
  "answer": "...",
  "confidence": "high|medium|low|not_found",
  "source_notebook": "local|global",
  "citations": [{"citation_number": 1, "text": "..."}],
  "next_action": {
    "type": "suggest_research",
    "message": "...",
    "command": "nlm research --topic \"...\" --add-sources --project-path \".\""
  }
}
```

`next_action` is only present when `confidence` is `low` or `not_found` and `--on-low-confidence` is `prompt` (the default).

## Auto-trigger

Call `nlm ask` when you encounter uncertainty about:
- Domain-specific concepts in this project (algorithms, specs, standards)
- Architecture decisions or design patterns documented in notebooks
- Technical terms you cannot confidently answer from the codebase alone

Do NOT call for: general programming questions, public API docs,
syntax questions, or anything answerable from code in the current repo.

## Handling results

| confidence | next_action present? | Action |
|------------|----------------------|--------|
| `high` / `medium` | No | Use answer directly |
| `low` | Yes (`suggest_research`) | Tell user coverage is limited; offer to run `/nlm-research` |
| `not_found` | Yes (`suggest_research`) | Tell user notebook has no relevant content; suggest `/nlm-research` or `--scope global` |
| any | No (`auto_researched: true`) | Sources were auto-added; answer reflects newly imported content |
```

- [ ] **Step 2: Verify the file looks correct**

```bash
cat /Users/marine/Code/NotebookLM\ SKILL/marine-notebooklm-skill/skills/nlm-ask/SKILL.md
```

- [ ] **Step 3: Commit**

```bash
git add skills/nlm-ask/SKILL.md
git commit -m "docs(nlm-ask): add auto-trigger rules, result handling table, on-low-confidence param"
```

---

## Task 8: Deploy and push

- [ ] **Step 1: Deploy to `~/.claude/skills/`**

```bash
rsync -av --delete \
  /Users/marine/Code/NotebookLM\ SKILL/marine-notebooklm-skill/scripts/ \
  ~/.claude/skills/nlm/scripts/

rsync -av --delete \
  /Users/marine/Code/NotebookLM\ SKILL/marine-notebooklm-skill/skills/ \
  ~/.claude/skills/nlm/skills/

for skill in nlm-ask nlm-plan nlm-research nlm-add nlm-setup nlm-migrate; do
  cp /Users/marine/Code/NotebookLM\ SKILL/marine-notebooklm-skill/skills/$skill/SKILL.md \
     ~/.claude/skills/$skill/SKILL.md
done

cp /Users/marine/Code/NotebookLM\ SKILL/marine-notebooklm-skill/SKILL.md \
   ~/.claude/skills/nlm/SKILL.md
```

- [ ] **Step 2: Install `anthropic` in the deployed venv (if not done in Task 1)**

```bash
~/.claude/skills/nlm/.venv/bin/pip install "anthropic>=0.40.0" -q
```

- [ ] **Step 3: Final end-to-end smoke test**

```bash
bash ~/.claude/skills/nlm/scripts/invoke.sh ask \
  --question "How does NSGA-III handle multi-objective voyage optimization?" \
  --scope auto \
  --on-low-confidence prompt \
  --project-path "." \
  --format json 2>&1 | python3 -m json.tool
```

Expected: well-formed JSON, `confidence` is `high` or `medium` for a SINAN-domain question.

- [ ] **Step 4: Push to GitHub**

```bash
cd /Users/marine/Code/NotebookLM\ SKILL/marine-notebooklm-skill
git push
```

---

## Self-Review Notes

- **Task 2 cache key:** Cache is stored as `{"notebooks": [...]}` with lowercase keys (`id`, `title`). The display table reformats to uppercase (`UUID`, `Title`). The router receives raw cache entries with lowercase keys — confirmed consistent throughout Tasks 2, 4, 6.
- **`_resolve_local_id` / `_resolve_global_ids`:** Already exist in `registry.py`; Task 6 requires verifying they are in the import block of `nlm.py`.
- **`anthropic` import in `notebook_router.py`:** Module-level import means missing API key raises at import time. This is acceptable — the fallback catches the exception from the `messages.create` call, not the import.
- **`research` mode scope:** Only fires on `local_nb_id`, never writes to global notebooks. Enforced by `confidence_handler.py` signature (`local_nb_id=None` path falls back to `prompt`).
