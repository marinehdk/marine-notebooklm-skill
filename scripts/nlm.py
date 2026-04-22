#!/usr/bin/env python3
"""nlm — NotebookLM skill CLI.

Usage:
  nlm ask --question "..." [--scope auto|local|global] [--format json|text]
  nlm plan --question "..." --options "A,B,C" [--criteria "x,y,z"]
  nlm research --topic "..." [--add-sources] [--depth fast|deep]
  nlm add --url URL | --note "text" [--title "title"]
  nlm setup [--auth] [--reauth] [--notebook-list] [--refresh] [--add-local-notebook UUID] [--add-global-notebook UUID ...] [--create-local TITLE] [--create-global TITLE] [--project-path PATH]
  nlm migrate --content "..." --target-global DOMAIN [--title TITLE]
"""

import argparse
import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from lib.auth import assert_authenticated, import_cookies_from_browser, is_authenticated, clear_auth
from lib.registry import (
    load_global_config, load_project_config,
    save_global_config, save_project_config,
    load_notebooks_cache, save_notebooks_cache,
    _resolve_local_id, _resolve_global_ids,
)
from lib.notebook_router import route_notebooks
from lib.confidence_handler import handle_confidence
from lib import client


def _do_browser_auth(force: bool = False) -> bool:
    """Open Chrome for Google login. Returns True if successful."""
    if not force and is_authenticated():
        print(json.dumps({"status": "ok", "authenticated": True, "message": "Already authenticated"}))
        return True
    try:
        result = import_cookies_from_browser()
        print(json.dumps({
            "status": "ok",
            "authenticated": True,
            "cookies_imported": result["cookies_imported"],
            "message": f"Authenticated — {result['cookies_imported']} cookies saved",
        }))
        return True
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}), file=sys.stderr)
        return False


def _next_step_after_local() -> dict:
    return {
        "hint": "可选：从列表中选择一个或多个全局参考笔记本",
        "commands": [
            "nlm setup --add-global-notebook <UUID>",
            "nlm setup --add-global-notebook <UUID1> <UUID2>",
        ],
        "skip": "如不需要，setup 已完成，可直接使用 nlm ask",
    }


def _next_step_after_global() -> dict:
    return {
        "hint": "Setup 完成，可继续追加更多全局参考本或开始使用",
        "commands": [
            'nlm ask --question "你的问题"',
            "nlm setup --add-global-notebook <UUID>",
        ],
    }


def cmd_setup(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="nlm setup")
    parser.add_argument("--auth", action="store_true")
    parser.add_argument("--reauth", action="store_true")
    parser.add_argument("--notebook-list", action="store_true")
    parser.add_argument("--refresh", action="store_true",
                        help="Force refresh notebook list from API (bypass cache)")
    parser.add_argument("--add-local-notebook", metavar="UUID",
                        help="Bind a notebook as the project local notebook")
    parser.add_argument("--add-global-notebook", nargs="+", metavar="UUID",
                        help="Append one or more notebooks as global references")
    parser.add_argument("--create-local", metavar="TITLE",
                        help="Create a new notebook and bind it as local")
    parser.add_argument("--create-global", metavar="TITLE",
                        help="Create a new notebook and append it as global")
    parser.add_argument("--status", action="store_true",
                        help="Show current notebook bindings without calling API")
    parser.add_argument("--project-path", default=".", metavar="PATH")
    parsed = parser.parse_args(args)

    project_path = Path(parsed.project_path).expanduser().resolve()

    # ── Auth ──────────────────────────────────────────────────────────────────
    if parsed.reauth:
        clear_auth()
        _do_browser_auth(force=True)
        return

    if parsed.auth:
        _do_browser_auth()
        return

    # ── Status (bare call or --status) ──────────────────────────────────────
    if parsed.status or not any([parsed.notebook_list, parsed.add_local_notebook,
                                 parsed.add_global_notebook, parsed.create_local,
                                 parsed.create_global]):
        config = load_project_config(project_path)
        print(json.dumps({
            "status": "ok",
            "authenticated": is_authenticated(),
            "project_path": str(project_path),
            "local_notebook": config.get("local_notebook"),
            "global_notebooks": config.get("global_notebooks", []),
            "next_step": None,
        }, indent=2, ensure_ascii=False))
        return

    if parsed.refresh and not parsed.notebook_list:
        print(json.dumps({"warning": "--refresh has no effect without --notebook-list"}), file=sys.stderr)

    assert_authenticated()

    # ── Notebook list (with cache) ────────────────────────────────────────────
    if parsed.notebook_list:
        cache = None if parsed.refresh else load_notebooks_cache(project_path)
        cached = cache is not None

        if not cached:
            raw = client.list_notebooks()
            # Enrich with AI descriptions (parallel fetch)
            nb_ids = [nb["id"] for nb in raw]
            descriptions = client.get_notebook_descriptions(nb_ids)
            for nb in raw:
                desc = descriptions.get(nb["id"], {"summary": "", "topics": []})
                nb["summary"] = desc["summary"]
                nb["topics"] = desc["topics"]
            save_notebooks_cache(project_path, raw)
            # Build response from raw; no need to reload from disk
            from datetime import datetime
            notebooks = raw
            cache_info = {
                "cached": False,
                "cached_at": datetime.now().isoformat(timespec="seconds"),
                "ttl_hours": 24,
            }
        else:
            notebooks = cache["notebooks"]
            cache_info = {
                "cached": True,
                "cached_at": cache["cached_at"],
                "ttl_hours": cache["ttl_hours"],
            }

        table = [
            {
                "#": i + 1,
                "UUID": nb["id"],
                "Title": nb["title"],
                "Sources": nb.get("source_count", 0),
                "Description": nb.get("description", ""),
                "Created": nb.get("created_at", "")[:16].replace("T", " "),
            }
            for i, nb in enumerate(notebooks)
        ]
        print(json.dumps({
            "action": "select_notebook",
            "cache": cache_info,
            "total": len(notebooks),
            "table": table,
            "next_step": {
                "hint": "选择一个作为本项目的 Local 笔记本，或新建一个",
                "commands": [
                    "nlm setup --add-local-notebook <UUID>",
                    'nlm setup --create-local "<新笔记本名称>"',
                ],
            },
        }, indent=2, ensure_ascii=False))
        return

    # ── Helpers: lookup notebook metadata from cache ──────────────────────────
    _meta_cache = load_notebooks_cache(project_path)

    def _get_nb_meta(uuid: str) -> dict:
        """Fetch notebook metadata from pre-loaded cache. Returns minimal stub if not found."""
        if _meta_cache:
            for nb in _meta_cache["notebooks"]:
                if nb["id"] == uuid:
                    return {
                        "id": nb["id"],
                        "title": nb.get("title", uuid[:12]),
                        "source_count": nb.get("source_count", 0),
                        "description": nb.get("description", ""),
                    }
        return {"id": uuid, "title": uuid[:12], "source_count": 0, "description": ""}

    # ── Add local notebook ────────────────────────────────────────────────────
    if parsed.add_local_notebook:
        uuid = parsed.add_local_notebook
        meta = _get_nb_meta(uuid)
        config = load_project_config(project_path)
        config["local_notebook"] = meta
        if "global_notebooks" not in config:
            config["global_notebooks"] = []
        config.pop("local_notebook_id", None)
        config.pop("global_notebook_ids", None)
        save_project_config(project_path, config)
        print(json.dumps({
            "status": "ok",
            "bound": "local",
            "local_notebook": meta,
            "next_step": _next_step_after_local(),
        }, indent=2, ensure_ascii=False))
        return

    # ── Add global notebooks ──────────────────────────────────────────────────
    if parsed.add_global_notebook:
        config = load_project_config(project_path)
        existing_global = config.get("global_notebooks", [])
        existing_ids = {nb["id"] for nb in existing_global}
        added = []
        for uuid in parsed.add_global_notebook:
            if uuid not in existing_ids:
                meta = _get_nb_meta(uuid)
                existing_global.append(meta)
                added.append(meta)
                existing_ids.add(uuid)
        config["global_notebooks"] = existing_global
        if "local_notebook" not in config:
            config["local_notebook"] = None
        config.pop("global_notebook_ids", None)
        save_project_config(project_path, config)
        print(json.dumps({
            "status": "ok",
            "bound": "global",
            "added": added,
            "global_notebooks_total": len(existing_global),
            "next_step": _next_step_after_global(),
        }, indent=2, ensure_ascii=False))
        return

    # ── Create local ──────────────────────────────────────────────────────────
    if parsed.create_local:
        nb = client.create_notebook(parsed.create_local)
        meta = {"id": nb["id"], "title": nb["title"], "source_count": 0, "description": ""}
        config = load_project_config(project_path)
        config["local_notebook"] = meta
        if "global_notebooks" not in config:
            config["global_notebooks"] = []
        config.pop("local_notebook_id", None)
        config.pop("global_notebook_ids", None)
        save_project_config(project_path, config)
        print(json.dumps({
            "status": "ok",
            "bound": "local",
            "created": True,
            "local_notebook": meta,
            "next_step": _next_step_after_local(),
        }, indent=2, ensure_ascii=False))
        return

    # ── Create global ─────────────────────────────────────────────────────────
    if parsed.create_global:
        nb = client.create_notebook(parsed.create_global)
        meta = {"id": nb["id"], "title": nb["title"], "source_count": 0, "description": ""}
        config = load_project_config(project_path)
        existing_global = config.get("global_notebooks", [])
        existing_global.append(meta)
        config["global_notebooks"] = existing_global
        if "local_notebook" not in config:
            config["local_notebook"] = None
        config.pop("global_notebook_ids", None)
        save_project_config(project_path, config)
        print(json.dumps({
            "status": "ok",
            "bound": "global",
            "created": True,
            "added": [meta],
            "global_notebooks_total": len(existing_global),
            "next_step": _next_step_after_global(),
        }, indent=2, ensure_ascii=False))
        return


def cmd_ask(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="nlm ask")
    parser.add_argument("--question", required=True)
    parser.add_argument("--scope", choices=["auto", "local", "global"], default="auto")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    parser.add_argument("--project-path", default=".")
    parser.add_argument(
        "--on-low-confidence",
        choices=["prompt", "research", "silent"],
        default="research",
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

    # Deduplicate citations by text content
    if result.get("citations"):
        seen: set[str] = set()
        deduped = []
        for cite in result["citations"]:
            key = cite.get("text", "") if isinstance(cite, dict) else str(cite)
            if key not in seen:
                seen.add(key)
                deduped.append(cite)
        # Renumber sequentially
        for i, cite in enumerate(deduped, 1):
            if isinstance(cite, dict):
                cite["citation_number"] = i
        result["citations"] = deduped

    if parsed.format == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"\n📝 Answer:\n{result['answer']}\n")
        print(f"🎯 Confidence: {result['confidence']} (from {source_notebook} notebook)")
        if result.get("citations"):
            print(f"📚 {len(result['citations'])} citation(s)")
        if result.get("next_action"):
            print(f"\n💡 {result['next_action']['message']}")


def cmd_plan(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="nlm plan")
    parser.add_argument("--question", required=True)
    parser.add_argument("--options", required=True, help="Comma-separated options e.g. 'A,B,C'")
    parser.add_argument("--criteria", default="", help="Comma-separated evaluation criteria")
    parser.add_argument("--max-research", type=int, default=3, dest="max_research")
    parser.add_argument("--project-path", default=".")
    parsed = parser.parse_args(args)

    assert_authenticated()
    project_path = Path(parsed.project_path).expanduser().resolve()

    options = [o.strip() for o in parsed.options.split(",") if o.strip()]
    criteria = [c.strip() for c in parsed.criteria.split(",") if c.strip()] if parsed.criteria else []

    from lib.plan_evaluator import PlanEvaluator
    evaluator = PlanEvaluator(project_path, max_research=parsed.max_research)

    if not evaluator._local_nb_id and not evaluator._global_nb_ids:
        print(json.dumps({"error": "No notebooks configured. Run: nlm setup"}))
        sys.exit(1)

    if not criteria:
        criteria = evaluator.propose_criteria(parsed.question)

    result = evaluator.evaluate(parsed.question, options, criteria)
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_research(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="nlm research")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--depth", choices=["fast", "deep"], default="fast")
    parser.add_argument("--add-sources", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--project-path", default=".")
    parsed = parser.parse_args(args)

    assert_authenticated()
    project_path = Path(parsed.project_path).expanduser().resolve()

    # Both cases require a local notebook (for context and/or import)
    cfg = load_project_config(project_path)
    notebook_id = _resolve_local_id(cfg)
    if not notebook_id:
        print(json.dumps({"error": "No local notebook configured. Run: nlm setup"}))
        sys.exit(1)

    print(f"🔍 Starting {parsed.depth} research: {parsed.topic[:60]}...", file=sys.stderr)
    result = client.research(notebook_id, parsed.topic, mode=parsed.depth)

    if result["status"] == "timeout":
        print(json.dumps({"error": "Research timed out after 180s", "topic": parsed.topic}))
        sys.exit(1)

    if result["status"] == "error":
        print(json.dumps({"error": "Research failed to start", "topic": parsed.topic}))
        sys.exit(1)

    sources_imported = []
    if parsed.add_sources and result.get("task_id") and result.get("sources"):
        print(f"📥 Importing {len(result['sources'])} sources into notebook...", file=sys.stderr)
        sources_imported = client.import_research_sources(
            notebook_id, result["task_id"], result["sources"]
        )

    print(json.dumps({
        "status": "ok",
        "topic": parsed.topic,
        "report": result.get("report", ""),
        "sources": result.get("sources", []),
        "sources_imported": len(sources_imported),
        "add_sources": parsed.add_sources,
    }, indent=2, ensure_ascii=False))


def cmd_add(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="nlm add")
    parser.add_argument("--url", help="Add a web URL as source")
    parser.add_argument("--note", help="Add text content as a note")
    parser.add_argument("--title", default="Note", help="Title for text note")
    parser.add_argument("--project-path", default=".")
    parsed = parser.parse_args(args)

    if not parsed.url and not parsed.note:
        print(json.dumps({"error": "Provide --url or --note"}))
        sys.exit(1)

    assert_authenticated()
    project_path = Path(parsed.project_path).expanduser().resolve()
    cfg = load_project_config(project_path)
    notebook_id = _resolve_local_id(cfg)

    if not notebook_id:
        print(json.dumps({"error": "No local notebook configured. Run: nlm setup"}))
        sys.exit(1)

    if parsed.url:
        result = client.add_url(notebook_id, parsed.url)
        print(json.dumps({"status": "ok", "type": "url", "source": result}, indent=2, ensure_ascii=False))
    else:
        result = client.add_note(notebook_id, title=parsed.title, content=parsed.note)
        print(json.dumps({"status": "ok", "type": "note", "note": result}, indent=2, ensure_ascii=False))


def cmd_migrate(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="nlm migrate")
    parser.add_argument("--content", required=True, help="Knowledge content to migrate")
    parser.add_argument("--target-global", required=True, metavar="DOMAIN",
                        help="Domain name of target global notebook")
    parser.add_argument("--title", default="Migrated Knowledge", help="Source title")
    parsed = parser.parse_args(args)

    assert_authenticated()
    global_cfg = load_global_config()
    domain = parsed.target_global.lower()

    target_id = None
    for nb in global_cfg.get("notebooks", []):
        if nb.get("domain", "").lower() == domain or nb.get("name", "").lower() == domain:
            target_id = nb.get("id")
            break

    if not target_id:
        available = [nb.get("domain") or nb.get("name") for nb in global_cfg.get("notebooks", [])]
        print(json.dumps({
            "error": f"No global notebook found for domain '{domain}'",
            "available_domains": available,
        }))
        sys.exit(1)

    result = client.add_text(target_id, title=parsed.title, content=parsed.content)
    print(json.dumps({
        "status": "ok",
        "migrated_to": domain,
        "notebook_id": target_id,
        "source": result,
    }, indent=2, ensure_ascii=False))


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    command = sys.argv[1]
    args = sys.argv[2:]

    if command == "setup":
        cmd_setup(args)
    elif command == "ask":
        cmd_ask(args)
    elif command == "plan":
        cmd_plan(args)
    elif command == "research":
        cmd_research(args)
    elif command == "add":
        cmd_add(args)
    elif command == "migrate":
        cmd_migrate(args)
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
