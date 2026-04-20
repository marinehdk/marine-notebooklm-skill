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
import json
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


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    command = sys.argv[1]
    args = sys.argv[2:]

    if command == "setup":
        cmd_setup(args)
    elif command in ("ask", "plan", "research", "add", "migrate"):
        print(json.dumps({"error": f"Command '{command}' not yet implemented"}))
        sys.exit(1)
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
