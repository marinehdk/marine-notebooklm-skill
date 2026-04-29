#!/usr/bin/env python3
"""nlm — NotebookLM skill CLI.

Usage:
  nlm ask --question "..." [--scope auto|local|global|synthesis|domain:<key>] [--format json|text]
  nlm plan --question "..." --options "A,B,C" [--criteria "x,y,z"]
  nlm research --topic "..." [--target auto|local|synthesis|domain:<key>] [--add-sources] [--depth fast|deep]
  nlm add --url URL | --note "text" [--title "title"]
  nlm setup [--auth] [--reauth] [--notebook-list] [--add-local-notebook UUID]
            [--add-global-notebook UUID ...] [--create-local TITLE] [--create-global TITLE]
            [--create-domain TITLE --domain-key KEY --domain-keywords KW1,KW2]
            [--create-synthesis TITLE] [--project-path PATH]
  nlm migrate --content "..." --target-global DOMAIN [--title TITLE]
  nlm topic [--clear] [--project-path PATH]
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
    _resolve_synthesis_id, _resolve_domain_notebooks,
)
from lib.notebook_router import route_notebooks
from lib.confidence_handler import handle_confidence
from lib.domain_classifier import classify_domain
from lib.domain_guard import check_new_domain, check_merge_candidates, check_split_candidates
from lib.bibliography import parse_bibliography_urls
from lib import client

_DISTILL_TRIGGER = 270  # Suggest synthesis distillation above this source count

# NLM Multi-Tier spec §3 — notebook naming convention: "{SCOPE} · {Name} · {Type}"
_TIER_TYPE = {
    "PROJ": "Local",
    "GLOBAL": "Reference",
    "DOMAIN": "Research",
    "META": "Synthesis",
}


def _format_tier_title(scope: str, name: str) -> str:
    """Wrap a user-supplied name per NLM Multi-Tier spec §3."""
    return f"{scope} · {name} · {_TIER_TYPE[scope]}"


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
                        help="Create a new notebook (auto-named 'PROJ · TITLE · Local') and bind it as local")
    parser.add_argument("--create-global", metavar="TITLE",
                        help="Create a new notebook (auto-named 'GLOBAL · TITLE · Reference') and append it as global")
    parser.add_argument("--create-domain", metavar="TITLE",
                        help="Create a domain notebook (auto-named 'DOMAIN · TITLE · Research'). Requires --domain-key and --domain-keywords")
    parser.add_argument("--domain-key", metavar="KEY",
                        help="Snake_case key for the domain (e.g. navigation_algorithms)")
    parser.add_argument("--domain-keywords", metavar="KEYWORDS",
                        help="Comma-separated keywords for domain routing (e.g. COLREGS,path planning)")
    parser.add_argument("--domain-description", metavar="DESC", default="",
                        help="Human-readable description of the domain")
    parser.add_argument("--create-synthesis", metavar="TITLE",
                        help="Create a synthesis notebook (auto-named 'META · TITLE · Synthesis') for cross-domain queries")
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
                                 parsed.create_global, parsed.create_domain,
                                 parsed.create_synthesis]):
        config = load_project_config(project_path)
        print(json.dumps({
            "status": "ok",
            "authenticated": is_authenticated(),
            "project_path": str(project_path),
            "local_notebook": config.get("local_notebook"),
            "global_notebooks": config.get("global_notebooks", []),
            "synthesis_notebook": config.get("synthesis_notebook"),
            "domain_notebooks": config.get("domain_notebooks", {}),
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
        title = _format_tier_title("PROJ", parsed.create_local)
        nb = client.create_notebook(title)
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
        title = _format_tier_title("GLOBAL", parsed.create_global)
        nb = client.create_notebook(title)
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

    # ── Create domain notebook ────────────────────────────────────────────────
    if parsed.create_domain:
        if not parsed.domain_key:
            print(json.dumps({"error": "--domain-key is required with --create-domain (e.g. navigation_algorithms)"}))
            sys.exit(1)
        if not parsed.domain_keywords:
            print(json.dumps({"error": "--domain-keywords is required with --create-domain (e.g. 'COLREGS,path planning,collision avoidance')"}))
            sys.exit(1)

        domain_key = parsed.domain_key.lower().replace(" ", "_").replace("-", "_")
        keywords = [kw.strip() for kw in parsed.domain_keywords.split(",") if kw.strip()]

        config = load_project_config(project_path)
        existing_domains = config.get("domain_notebooks", {})
        if domain_key in existing_domains:
            print(json.dumps({
                "error": f"Domain '{domain_key}' already exists.",
                "existing": existing_domains[domain_key],
            }))
            sys.exit(1)

        title = _format_tier_title("DOMAIN", parsed.create_domain)
        nb = client.create_notebook(title)
        domain_meta = {
            "id": nb["id"],
            "name": title,
            "description": parsed.domain_description,
            "keywords": keywords,
            "source_count": 0,
            "last_distilled": None,
        }
        existing_domains[domain_key] = domain_meta
        config["domain_notebooks"] = existing_domains
        save_project_config(project_path, config)
        print(json.dumps({
            "status": "ok",
            "bound": "domain",
            "created": True,
            "domain_key": domain_key,
            "domain_notebook": domain_meta,
            "total_domains": len(existing_domains),
            "next_step": {
                "hint": "域笔记本已创建。运行 /nlm-research 时来源将自动路由至此。",
                "commands": [
                    f'nlm research --topic "你的领域话题" --target domain:{domain_key}',
                    f'nlm ask --question "你的领域问题" --scope domain:{domain_key}',
                ],
            },
        }, indent=2, ensure_ascii=False))
        return

    # ── Create synthesis notebook ──────────────────────────────────────────────
    if parsed.create_synthesis:
        config = load_project_config(project_path)
        if config.get("synthesis_notebook"):
            print(json.dumps({
                "error": "Synthesis notebook already configured.",
                "synthesis_notebook": config["synthesis_notebook"],
            }))
            sys.exit(1)

        title = _format_tier_title("META", parsed.create_synthesis)
        nb = client.create_notebook(title)
        synthesis_meta = {"id": nb["id"], "name": title, "source_count": 0, "last_distilled": None}
        config["synthesis_notebook"] = synthesis_meta
        save_project_config(project_path, config)
        print(json.dumps({
            "status": "ok",
            "bound": "synthesis",
            "created": True,
            "synthesis_notebook": synthesis_meta,
            "next_step": {
                "hint": "母笔记本已创建。当域笔记本超过 270 来源时，蒸馏 Briefing Doc 后通过 nlm-add 导入此本。",
                "commands": ["nlm add --note '<Briefing Doc内容>' --title '<域名> Briefing' --target synthesis"],
            },
        }, indent=2, ensure_ascii=False))
        return


def cmd_ask(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="nlm ask")
    parser.add_argument("--question", required=True)
    parser.add_argument(
        "--scope", default="auto",
        help="auto (default), local, global, synthesis, domain:<key>, or all",
    )
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
    synthesis_id = _resolve_synthesis_id(config)
    domain_notebooks = _resolve_domain_notebooks(config)

    if not local_nb_id and not global_nb_ids and not domain_notebooks and not synthesis_id:
        print(json.dumps({"error": "No notebooks configured. Run: nlm setup"}))
        sys.exit(1)

    # Build lookup from cache for router metadata
    cache = load_notebooks_cache(project_path)
    cache_by_id: dict[str, dict] = {}
    if cache:
        for nb in cache.get("notebooks", []):
            cache_by_id[nb["id"]] = nb

    from lib.progress import step, done, info, warn

    result = None
    answered_by: list[str] = []

    # ── Scope: local ──────────────────────────────────────────────────────────
    if parsed.scope == "local":
        if not local_nb_id:
            print(json.dumps({"error": "No local notebook configured. Run: nlm setup"}))
            sys.exit(1)
        step(1, 1, "Querying local notebook...")
        result = client.ask(local_nb_id, parsed.question)
        answered_by = ["local"]
        done(1, 1, f"Got answer (confidence: {result['confidence']})")

    # ── Scope: global ─────────────────────────────────────────────────────────
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
        for i, nb_id in enumerate(ranked, 1):
            step(i, len(ranked), f"Querying global notebook {i}/{len(ranked)}...")
            r = client.ask(nb_id, parsed.question)
            nb_title = cache_by_id.get(nb_id, {}).get("title", nb_id[:8])
            if r["confidence"] not in ("low", "not_found"):
                result = r
                answered_by = [f"global:{nb_title}"]
                done(i, len(ranked), f"Got answer (confidence: {r['confidence']})")
                break
            info("Low confidence, trying next notebook...")
            result = r
            answered_by = [f"global:{nb_title}"]

    # ── Scope: synthesis ──────────────────────────────────────────────────────
    elif parsed.scope == "synthesis":
        if not synthesis_id:
            print(json.dumps({"error": "No synthesis notebook configured. Run: nlm setup --create-synthesis \"<title>\""}))
            sys.exit(1)
        step(1, 1, "Querying synthesis notebook...")
        result = client.ask(synthesis_id, parsed.question)
        answered_by = ["synthesis"]
        done(1, 1, f"Got answer (confidence: {result['confidence']})")

    # ── Scope: domain:<key> ───────────────────────────────────────────────────
    elif parsed.scope.startswith("domain:"):
        key = parsed.scope[len("domain:"):]
        if key not in domain_notebooks:
            print(json.dumps({"error": f"Domain '{key}' not found in config.", "available": list(domain_notebooks.keys())}))
            sys.exit(1)
        domain_nb_id = domain_notebooks[key].get("id")
        if not domain_nb_id:
            print(json.dumps({"error": f"Domain '{key}' has no notebook ID."}))
            sys.exit(1)
        step(1, 1, f"Querying domain notebook '{key}'...")
        result = client.ask(domain_nb_id, parsed.question)
        answered_by = [f"domain:{key}"]
        done(1, 1, f"Got answer (confidence: {result['confidence']})")
        # Fallback to local on low confidence
        if result.get("confidence") in ("low", "not_found") and local_nb_id:
            info(f"Domain '{key}' low confidence, checking local notebook...")
            r = client.ask(local_nb_id, parsed.question)
            if r["confidence"] not in ("low", "not_found"):
                result = r
                answered_by = ["local"]
                done(1, 1, f"Local answered (confidence: {r['confidence']})")
            else:
                answered_by.append("local")

    # ── Scope: auto ───────────────────────────────────────────────────────────
    else:  # auto (and unrecognised values fall through gracefully)
        # Phase 1: classify question to find relevant domain
        routing = classify_domain(parsed.question, project_path)
        if routing.startswith("NEW:") or routing == "local" or not domain_notebooks:
            target_domain_key = None
        else:
            target_domain_key = routing

        # Phase 2a: query domain notebook if matched
        if target_domain_key and target_domain_key in domain_notebooks:
            domain_nb_id = domain_notebooks[target_domain_key].get("id")
            if domain_nb_id:
                info(f"Domain classified as '{target_domain_key}', querying domain notebook...")
                step(1, 1, f"Querying domain notebook '{target_domain_key}'...")
                result = client.ask(domain_nb_id, parsed.question)
                answered_by = [f"domain:{target_domain_key}"]
                done(1, 1, f"Got answer (confidence: {result['confidence']})")

        # Phase 2b: query local notebook (always, or as fallback)
        if result is None or result.get("confidence") in ("low", "not_found"):
            if local_nb_id:
                if result is not None:
                    info("Domain confidence low, checking local notebook...")
                step(1, 1, "Querying local notebook...")
                r = client.ask(local_nb_id, parsed.question)
                if r["confidence"] not in ("low", "not_found") or result is None:
                    result = r
                    answered_by = ["local"]
                done(1, 1, f"Got answer (confidence: {r['confidence']})")

        # Phase 3: escalate to global notebooks if still low confidence
        if (result is None or result.get("confidence") in ("low", "not_found")) and global_nb_ids:
            info("Still low confidence, escalating to global notebooks...")
            global_pool = [cache_by_id[uid] for uid in global_nb_ids if uid in cache_by_id]
            if global_pool and any(nb.get("summary") for nb in global_pool):
                route = route_notebooks(parsed.question, global_pool)
                ranked = route.ranked_ids or global_nb_ids[:3]
            else:
                ranked = global_nb_ids[:3]
            for nb_id in ranked:
                if nb_id == local_nb_id:
                    continue
                step(1, 1, "Querying global notebook...")
                r = client.ask(nb_id, parsed.question)
                nb_title = cache_by_id.get(nb_id, {}).get("title", nb_id[:8])
                if r["confidence"] not in ("low", "not_found"):
                    result = r
                    answered_by = [f"global:{nb_title}"]
                    done(1, 1, f"Got answer (confidence: {r['confidence']})")
                    break
                result = r
                answered_by = [f"global:{nb_title}"]

        # Phase 4: synthesis as last resort for cross-domain questions
        if (result is None or result.get("confidence") in ("low", "not_found")) and synthesis_id:
            info("Checking synthesis notebook...")
            r = client.ask(synthesis_id, parsed.question)
            if r["confidence"] not in ("low", "not_found"):
                result = r
                answered_by = ["synthesis"]
            elif result is None:
                result = r
                answered_by = ["synthesis"]

    if result is None:
        print(json.dumps({
            "error": "No notebooks available to query",
            "suggest_research": True,
        }))
        sys.exit(1)

    result["answered_by"] = answered_by
    result["source_notebook"] = answered_by[0] if answered_by else "unknown"

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

    # Record question to topic profile (silent — never blocks the answer)
    try:
        from lib.topic_tracker import TopicTracker
        TopicTracker(project_path).record_ask(parsed.question)
    except Exception:
        pass

    # Surface suggest_research when no useful answer was found
    if result.get("confidence") in ("low", "not_found"):
        result["suggest_research"] = True

    if parsed.format == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        nb_label = ", ".join(answered_by) if answered_by else "unknown"
        print(f"\n📝 Answer:\n{result['answer']}\n")
        print(f"🎯 Confidence: {result['confidence']} (from: {nb_label})")
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
    parser.add_argument(
        "--target", default="auto",
        help="Target notebook: auto (default), local, synthesis, or domain:<key>",
    )
    parser.add_argument(
        "--max-import", type=int, default=None,
        help="Hard cap on sources imported this run. Default: import all found sources.",
    )
    parser.add_argument(
        "--min-relevance", type=float, default=0.1,
        help="Sources scoring below this threshold are deleted after every import. Default: 0.1.",
    )
    parser.add_argument("--project-path", default=".")
    parsed = parser.parse_args(args)

    assert_authenticated()
    project_path = Path(parsed.project_path).expanduser().resolve()

    cfg = load_project_config(project_path)
    from lib.progress import step, done, warn, info

    # ── Resolve target notebook via --target routing ──────────────────────────
    domain_suggestion: dict | None = None
    target_notebook_name: str = "local"

    if parsed.target == "auto":
        routing = classify_domain(parsed.topic, project_path)
        if routing.startswith("NEW:"):
            domain_suggestion = {
                "type": "new_domain_suggested",
                "suggested_name": routing[4:],
                "message": (
                    f"Topic '{parsed.topic}' doesn't match any existing domain. "
                    f"Suggested new domain: '{routing[4:]}'. "
                    "Routing to local notebook for this run. "
                    "To create the domain: nlm setup --create-domain \"<title>\" "
                    "--domain-key <key> --domain-keywords \"kw1,kw2\""
                ),
            }
            notebook_id = _resolve_local_id(cfg)
            target_notebook_name = "local"
        elif routing == "local":
            notebook_id = _resolve_local_id(cfg)
            target_notebook_name = "local"
        else:
            # routing is a domain_key
            domain_nbs = _resolve_domain_notebooks(cfg)
            if nb_entry := domain_nbs.get(routing):
                notebook_id = nb_entry.get("id")
                target_notebook_name = f"domain:{routing}"
            else:
                notebook_id = _resolve_local_id(cfg)
                target_notebook_name = "local"
    elif parsed.target == "local":
        notebook_id = _resolve_local_id(cfg)
        target_notebook_name = "local"
    elif parsed.target == "synthesis":
        notebook_id = _resolve_synthesis_id(cfg)
        target_notebook_name = "synthesis"
    elif parsed.target.startswith("domain:"):
        key = parsed.target[len("domain:"):]
        domain_nbs = _resolve_domain_notebooks(cfg)
        if nb_entry := domain_nbs.get(key):
            notebook_id = nb_entry.get("id")
            target_notebook_name = f"domain:{key}"
        else:
            print(json.dumps({"error": f"Domain '{key}' not found in config. Run: nlm setup --notebook-list"}))
            sys.exit(1)
    else:
        print(json.dumps({"error": f"Unknown --target value: '{parsed.target}'. Use: auto, local, synthesis, or domain:<key>"}))
        sys.exit(1)

    if not notebook_id:
        print(json.dumps({"error": "No notebook resolved for target. Run: nlm setup"}))
        sys.exit(1)

    from lib.topic_tracker import TopicTracker

    # Record research topic to the project profile (weight=2: intentional signal)
    tracker = TopicTracker(project_path)
    tracker.record_research(parsed.topic)
    topic_weights = tracker.keyword_weights()

    # --max-import 0 means skip import
    if parsed.max_import == 0:
        parsed.add_sources = False

    total = 4 if parsed.add_sources else 1
    timeout_label = "60s" if parsed.depth == "fast" else "600s"

    step(1, total, f"Starting {parsed.depth} research (timeout: {timeout_label}): {parsed.topic[:60]}...")
    result = client.research(notebook_id, parsed.topic, mode=parsed.depth)

    if result["status"] == "timeout":
        warn(f"Research timed out after {timeout_label}")
        print(json.dumps({"error": f"Research timed out after {timeout_label}", "topic": parsed.topic}))
        sys.exit(1)
    if result["status"] == "error":
        warn("Research failed to start")
        print(json.dumps({"error": "Research failed to start", "topic": parsed.topic}))
        sys.exit(1)

    all_sources = result.get("sources", [])
    n_found = len(all_sources)
    # GAP-12/GAP-9: parse bibliography to find cited URLs (replaces dead cited_in_report field)
    cited_urls: set[str] = parse_bibliography_urls(result.get("report", ""))
    n_cited = len(cited_urls)  # GAP-11: was result.get("sources_cited_count", 0) — always 0
    cite_note = f" ({n_cited} cited in report)" if n_cited else ""
    done(1, total, f"Research complete — {n_found} sources found{cite_note}")

    sources_imported = []
    duplicates_removed = 0
    notebook_count = 0
    prune_result: dict = {"scored": [], "kept": 0, "pruned": 0, "notebook_count": 0}
    new_notebook_suggestion: str | None = None

    if parsed.add_sources and result.get("task_id") and all_sources:
        # GAP-9: use bibliography-parsed cited URLs instead of dead cited_in_report field.
        # deep research: import only sources whose URL was cited in the report bibliography.
        # fast research: report has no bibliography → cited_urls is empty → import all.
        if cited_urls:
            cited_lower = {u.rstrip("/").lower() for u in cited_urls}
            sources_to_import = [
                s for s in all_sources
                if (s.get("url") or "").rstrip("/").lower() in cited_lower
            ]
            if not sources_to_import:
                # URL format mismatch between bibliography and SDK source list — fall back
                import sys
                print(f"[nlm] warn: bibliography has {len(cited_urls)} URLs but none matched source list; importing all sources", file=sys.stderr)
                sources_to_import = all_sources
        else:
            sources_to_import = all_sources
        n_skipped = n_found - len(sources_to_import)

        cap_note = f" (capped at {parsed.max_import})" if parsed.max_import else ""
        skip_note = f", {n_skipped} uncited skipped" if n_skipped else ""
        step(2, total, f"Importing {len(sources_to_import)} sources{cap_note}{skip_note}...")
        try:
            sources_imported = client.import_research_sources(
                notebook_id, result["task_id"], sources_to_import,
                max_sources=parsed.max_import,
            )
            done(2, total, f"Imported {len(sources_imported)} new sources")
        except Exception as e:
            warn(f"Source import failed ({type(e).__name__}) — research results still shown below")

        step(3, total, "Deduplicating notebook sources...")
        dedup: dict = {"removed": 0, "failed_removed": 0, "kept": 0}
        try:
            dedup = client.deduplicate_notebook_sources(notebook_id)
            duplicates_removed = dedup.get("removed", 0)
            notebook_count = dedup.get("kept", 0)
            msg = f"Deduplication complete — {notebook_count} sources in notebook"
            if duplicates_removed:
                msg += f", {duplicates_removed} duplicates removed"
            done(3, total, msg)
        except Exception as e:
            warn(f"Deduplication failed ({type(e).__name__}) — skipped")

        # Step 4: score + prune newly imported sources on two dimensions:
        #   - topic relevance: accumulated topic profile (keyword_weights)
        #   - query contribution: current --topic keywords at 2× boost
        # Deletion runs on every import, not just near capacity.
        step(4, total, f"Scoring + pruning new sources ({notebook_count}/300)...")

        new_ids = [s["id"] for s in sources_imported if isinstance(s, dict) and "id" in s]

        if new_ids and notebook_count >= 250:  # spec §3.3.5: score only when near capacity
            from lib.topic_tracker import _extract_keywords
            query_kws = _extract_keywords(parsed.topic)
            combined_weights: dict[str, float] = dict(topic_weights)
            for kw in query_kws:
                combined_weights[kw] = combined_weights.get(kw, 0.0) + 2.0

            if combined_weights:
                try:
                    prune_result = client.score_and_prune_sources(
                        notebook_id, new_ids, combined_weights,
                    )
                    done(4, total,
                         f"Scored {len(prune_result['scored'])} sources — {notebook_count}/300 (no auto-delete)")
                except Exception as e:
                    warn(f"Relevance scoring failed ({type(e).__name__}) — skipped")
                    done(4, total, f"Scoring failed — {notebook_count}/300")
            else:
                done(4, total, f"No keywords — scoring skipped, {notebook_count}/300")
        else:
            reason = "no new sources" if not new_ids else f"notebook_count={notebook_count}<250"
            done(4, total, f"Scoring skipped ({reason}) — {notebook_count}/300")

        if notebook_count >= 250:  # NOTEBOOK_WARN_THRESHOLD
            new_notebook_suggestion = (
                f"Notebook has {notebook_count}/300 sources after pruning. "
                "Consider creating a new domain notebook: "
                "nlm setup --create-domain \"<Title>\" --domain-key <key> --domain-keywords \"kw1,kw2\""
            )
            warn(new_notebook_suggestion)

    # ── Post-import: update source_count in config for domain notebooks ───────
    if parsed.add_sources and notebook_count and target_notebook_name.startswith("domain:"):
        domain_key = target_notebook_name[len("domain:"):]
        try:
            cfg2 = load_project_config(project_path)
            if domain_key in cfg2.get("domain_notebooks", {}):
                cfg2["domain_notebooks"][domain_key]["source_count"] = notebook_count
                save_project_config(project_path, cfg2)
        except Exception:
            pass

    # ── Domain guard checks (merge + split candidates) ────────────────────────
    merge_suggestions = []
    split_suggestions = []
    try:
        merges = check_merge_candidates(project_path)
        merge_suggestions = [
            {"merge_from": m.merge_from, "merge_into": m.merge_into,
             "overlap": m.overlap, "combined_sources": m.combined_sources, "command": m.command}
            for m in merges
        ]
        splits = check_split_candidates(project_path)
        split_suggestions = [
            {"domain": s.domain, "source_count": s.source_count, "command": s.command, "reason": s.reason}
            for s in splits
        ]
    except Exception:
        pass

    out = {
        "status": "ok",
        "topic": parsed.topic,
        "target_notebook": target_notebook_name,
        "report": result.get("report", ""),
        "sources": result.get("sources", []),
        "sources_cited_count": n_cited,
        "sources_imported": len(sources_imported),
        "sources_pruned": prune_result["pruned"],
        "duplicates_removed": duplicates_removed,
        "notebook_source_count": notebook_count,
        "add_sources": parsed.add_sources,
    }
    if new_notebook_suggestion:
        out["new_notebook_suggestion"] = new_notebook_suggestion
    if domain_suggestion:
        out["domain_suggestion"] = domain_suggestion
    if merge_suggestions:
        out["merge_suggestions"] = merge_suggestions
    if split_suggestions:
        out["split_suggestions"] = split_suggestions
    if prune_result.get("scored"):
        out["relevance_scores"] = [
            {"id": r["id"], "score": r["score"], "kept": r["kept"],
             "keywords": r.get("keywords", [])}
            for r in prune_result["scored"]
        ]
    print(json.dumps(out, indent=2, ensure_ascii=False))


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
        if result.get("skipped"):
            print(json.dumps({
                "status": "skipped",
                "reason": "already_exists",
                "source": {"id": result["id"], "title": result["title"]},
            }, indent=2, ensure_ascii=False))
        else:
            print(json.dumps({"status": "ok", "type": "url", "source": result}, indent=2, ensure_ascii=False))
    else:
        result = client.add_note(notebook_id, title=parsed.title, content=parsed.note)
        print(json.dumps({"status": "ok", "type": "note", "note": result}, indent=2, ensure_ascii=False))


def cmd_delete(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="nlm delete")
    parser.add_argument("--url", help="Delete source matching this URL")
    parser.add_argument("--source-id", help="Delete source with this ID")
    parser.add_argument("--project-path", default=".")
    parsed = parser.parse_args(args)

    if not parsed.url and not parsed.source_id:
        print(json.dumps({"error": "Provide --url or --source-id"}))
        sys.exit(1)

    assert_authenticated()
    project_path = Path(parsed.project_path).expanduser().resolve()
    cfg = load_project_config(project_path)
    notebook_id = _resolve_local_id(cfg)
    if not notebook_id:
        print(json.dumps({"error": "No local notebook configured. Run: nlm setup"}))
        sys.exit(1)

    deleted = client.delete_source(
        notebook_id,
        source_id=parsed.source_id,
        url=parsed.url,
    )
    if deleted is None:
        key = parsed.url or parsed.source_id
        print(json.dumps({"status": "not_found", "key": key}))
        sys.exit(1)
    print(json.dumps({"status": "ok", "deleted": deleted}, indent=2, ensure_ascii=False))


def cmd_deduplicate(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="nlm deduplicate")
    parser.add_argument("--notebook-id", help="Target notebook UUID (overrides --project-path)")
    parser.add_argument("--project-path", default=".")
    parsed = parser.parse_args(args)

    assert_authenticated()

    if parsed.notebook_id:
        notebook_id = parsed.notebook_id
    else:
        project_path = Path(parsed.project_path).expanduser().resolve()
        cfg = load_project_config(project_path)
        notebook_id = _resolve_local_id(cfg)
        if not notebook_id:
            print(json.dumps({"error": "No local notebook configured. Run: nlm setup"}))
            sys.exit(1)

    result = client.deduplicate_notebook_sources(notebook_id)
    print(json.dumps({"status": "ok", "notebook_id": notebook_id, **result}, indent=2, ensure_ascii=False))


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


def cmd_topic(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="nlm topic")
    parser.add_argument("--project-path", default=".")
    parser.add_argument("--clear", action="store_true", help="Clear the topic profile for this project")
    parsed = parser.parse_args(args)

    project_path = Path(parsed.project_path).expanduser().resolve()

    from lib.topic_tracker import TopicTracker
    tracker = TopicTracker(project_path)

    if parsed.clear:
        topics_file = project_path / ".nlm" / "topics.json"
        if topics_file.exists():
            topics_file.unlink()
        print(json.dumps({"status": "ok", "message": "Topic profile cleared"}))
        return

    summary = tracker.summary()
    print(json.dumps({
        "status": "ok",
        "project_path": str(project_path),
        "total_entries": summary["total_entries"],
        "top_keywords": summary["top_keywords"],
        "note": "Relevance scoring is active" if summary["total_entries"] > 0
                else "No topics recorded yet — run /nlm-ask or /nlm-research first",
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
    elif command == "delete":
        cmd_delete(args)
    elif command == "deduplicate":
        cmd_deduplicate(args)
    elif command == "migrate":
        cmd_migrate(args)
    elif command == "topic":
        cmd_topic(args)
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
