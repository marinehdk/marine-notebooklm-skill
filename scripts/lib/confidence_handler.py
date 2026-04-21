"""Handle low-confidence ask results: prompt, research, or silent."""
from __future__ import annotations

from typing import Any

from lib import client as nlm_client


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
