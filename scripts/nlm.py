#!/usr/bin/env python3
"""nlm — NotebookLM skill CLI.

Usage:
  nlm ask --question "..." [--scope auto|local|global] [--format json|text]
  nlm plan --question "..." --options "A,B,C" [--criteria "x,y,z"]
  nlm research --topic "..." [--add-sources] [--depth fast|deep]
  nlm add --url URL | --note "text" [--title "title"]
  nlm setup [--project-path PATH] [--auth] [--create TITLE] [--notebook-id UUID]
  nlm migrate --content "..." --target-global DOMAIN [--title TITLE]
"""

import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from lib.auth import assert_authenticated, is_authenticated
from lib.registry import (
    find_notebook_ids, load_global_config, load_project_config,
    save_global_config, save_project_config,
)
from lib import client


def _setup_auth() -> bool:
    """Run notebooklm login to set up authentication. Returns True if successful."""
    try:
        # Use the system notebooklm CLI
        result = subprocess.run(
            ["/opt/homebrew/bin/notebooklm", "login"],
            text=True,
            timeout=300
        )
        return result.returncode == 0
    except Exception:
        return False


def cmd_setup(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="nlm setup")
    parser.add_argument("--project-path", default=".")
    parser.add_argument("--auth", action="store_true", help="Only check/setup auth")
    parser.add_argument("--create", metavar="TITLE", help="Create a new notebook with this title")
    parser.add_argument("--notebook-id", metavar="UUID", help="Use this notebook ID directly")
    parsed = parser.parse_args(args)

    project_path = Path(parsed.project_path).expanduser().resolve()

    if parsed.auth:
        if is_authenticated():
            print(json.dumps({"status": "ok", "authenticated": True}))
        else:
            # Try to authenticate
            success = _setup_auth()
            if success and is_authenticated():
                print(json.dumps({"status": "ok", "authenticated": True}))
            else:
                print(json.dumps({"status": "not_authenticated",
                                  "message": "Open browser to authenticate",
                                  "run": "notebooklm login"}))
        return

    assert_authenticated()

    # Resolve notebook ID
    notebook_id = None
    notebook_title = None

    if parsed.notebook_id:
        notebook_id = parsed.notebook_id
        notebook_title = notebook_id[:12]
    elif parsed.create:
        nb = client.create_notebook(parsed.create)
        notebook_id = nb["id"]
        notebook_title = nb["title"]
        print(f"✅ Created notebook: {notebook_title}", file=sys.stderr)
    else:
        # List all notebooks and let user choose
        notebooks = client.list_notebooks()
        if not notebooks:
            print(json.dumps({"error": "No notebooks found. Use --create to create one."}))
            sys.exit(1)
        output = {
            "action": "select_notebook",
            "message": "Re-run with --notebook-id <id> to configure this project",
            "notebooks": [{"index": i+1, "id": nb["id"], "title": nb["title"]}
                          for i, nb in enumerate(notebooks)],
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
        return

    # Save project config
    config = load_project_config(project_path)
    config["local_notebook_id"] = notebook_id
    if "global_notebook_ids" not in config:
        config["global_notebook_ids"] = []
    save_project_config(project_path, config)

    print(json.dumps({
        "status": "ok",
        "project_path": str(project_path),
        "local_notebook_id": notebook_id,
        "notebook_title": notebook_title,
    }, indent=2, ensure_ascii=False))


def cmd_ask(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="nlm ask")
    parser.add_argument("--question", required=True)
    parser.add_argument("--scope", choices=["auto", "local", "global"], default="auto")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    parser.add_argument("--project-path", default=".")
    parsed = parser.parse_args(args)

    assert_authenticated()
    project_path = Path(parsed.project_path).expanduser().resolve()
    notebook_ids = find_notebook_ids(parsed.scope, project_path)

    if not notebook_ids:
        print(json.dumps({"error": "No notebooks configured. Run: nlm setup"}))
        sys.exit(1)

    # Try notebooks in order; upgrade to global if local confidence is low/not_found
    result = None
    source_notebook = "unknown"

    for i, nb_id in enumerate(notebook_ids):
        is_local = (i == 0 and parsed.scope in ("local", "auto"))
        r = client.ask(nb_id, parsed.question)

        # In non-auto modes, always use first notebook
        if parsed.scope != "auto":
            result = r
            source_notebook = "local" if is_local else "global"
            break

        # In auto mode: use if confidence is good, otherwise try next
        if r["confidence"] not in ("low", "not_found"):
            result = r
            source_notebook = "local" if is_local else "global"
            break

        # Keep trying (result will be overwritten by next notebook)
        result = r
        source_notebook = "local" if is_local else "global"

    result["source_notebook"] = source_notebook

    if parsed.format == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"\n📝 Answer:\n{result['answer']}\n")
        print(f"🎯 Confidence: {result['confidence']} (from {source_notebook} notebook)")
        if result.get("citations"):
            print(f"📚 {len(result['citations'])} citation(s)")


def cmd_plan(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="nlm plan")
    parser.add_argument("--question", required=True)
    parser.add_argument("--options", required=True, help="Comma-separated options e.g. 'A,B,C'")
    parser.add_argument("--criteria", default="", help="Comma-separated evaluation criteria")
    parser.add_argument("--project-path", default=".")
    parsed = parser.parse_args(args)

    assert_authenticated()
    project_path = Path(parsed.project_path).expanduser().resolve()
    notebook_ids = find_notebook_ids("auto", project_path)

    if not notebook_ids:
        print(json.dumps({"error": "No notebooks configured. Run: nlm setup"}))
        sys.exit(1)

    notebook_id = notebook_ids[0]
    options = [o.strip() for o in parsed.options.split(",") if o.strip()]
    criteria = [c.strip() for c in parsed.criteria.split(",") if c.strip()] if parsed.criteria else []

    matrix: dict[str, dict] = {}
    answers: dict[str, str] = {}

    for option in options:
        if criteria:
            q = (f"Regarding: {parsed.question}\n"
                 f"Evaluate option '{option}' on these criteria: {', '.join(criteria)}. "
                 f"For each criterion, give a score (high/medium/low) and brief reason.")
        else:
            q = (f"Regarding: {parsed.question}\n"
                 f"What are the pros and cons of option '{option}'?")

        r = client.ask(notebook_id, q)
        answers[option] = r["answer"]
        if criteria:
            row: dict[str, str] = {}
            for criterion in criteria:
                criterion_lower = criterion.lower()
                answer_lower = r["answer"].lower()
                if criterion_lower in answer_lower:
                    # Simple heuristic: look for high/medium/low near criterion mention
                    idx = answer_lower.find(criterion_lower)
                    snippet = answer_lower[max(0, idx-20):idx+100]
                    if "high" in snippet or "excellent" in snippet or "strong" in snippet:
                        row[criterion] = "high"
                    elif "low" in snippet or "poor" in snippet or "weak" in snippet:
                        row[criterion] = "low"
                    else:
                        row[criterion] = "medium"
                else:
                    row[criterion] = "unknown"
            matrix[option] = row

    # Pick recommendation: option with most "high" scores
    recommendation = options[0]
    if matrix:
        scores = {opt: sum(1 for v in scores.values() if v == "high")
                  for opt, scores in matrix.items()}
        recommendation = max(scores, key=scores.get)

    print(json.dumps({
        "recommendation": recommendation,
        "rationale": answers.get(recommendation, "")[:500],
        "matrix": matrix,
        "raw_answers": answers,
    }, indent=2, ensure_ascii=False))


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
    notebook_id = cfg.get("local_notebook_id")
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
    notebook_id = cfg.get("local_notebook_id")

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
