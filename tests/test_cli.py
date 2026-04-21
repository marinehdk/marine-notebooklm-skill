"""Integration smoke tests — requires real NotebookLM auth and a configured project."""
import json
import subprocess
import sys
from pathlib import Path

INVOKE = str(Path.home() / ".claude/skills/nlm/scripts/invoke.sh")
PROJECT = "/tmp/nlm-test"


def run(args: list[str], expect_success: bool = True) -> dict:
    cmd = ["bash", INVOKE] + args
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=200)
    print(f"\n$ nlm {' '.join(args)}")
    print(f"stdout: {result.stdout[:300]}")
    if result.stderr:
        print(f"stderr: {result.stderr[:200]}")
    if expect_success:
        assert result.returncode == 0, f"Expected success, got exit {result.returncode}"
        return json.loads(result.stdout)
    else:
        assert result.returncode != 0, f"Expected failure, got exit 0"
        return {}


def test_setup_auth():
    out = run(["setup", "--auth"])
    assert out["status"] == "ok"
    assert out["authenticated"] is True


def test_ask_scope_auto_format_json():
    out = run(["ask", "--question", "What is this notebook about?",
               "--project-path", PROJECT, "--scope", "auto", "--format", "json"])
    assert "answer" in out
    assert out["confidence"] in ("high", "medium", "low", "not_found")
    assert "source_notebook" in out


def test_ask_scope_local_format_json():
    out = run(["ask", "--question", "Summarize the main topics",
               "--project-path", PROJECT, "--scope", "local", "--format", "json"])
    assert "answer" in out


def test_ask_format_text():
    result = subprocess.run(
        ["bash", INVOKE, "ask", "--question", "What topics are covered?",
         "--project-path", PROJECT, "--format", "text"],
        capture_output=True, text=True, timeout=60
    )
    assert result.returncode == 0
    assert "Answer:" in result.stdout
    assert "Confidence:" in result.stdout


def test_plan_two_options():
    out = run(["plan", "--question", "Which is better for this project?",
               "--options", "approach-A,approach-B",
               "--project-path", PROJECT])
    assert "recommendation" in out
    assert out["recommendation"] in ("approach-A", "approach-B")
    assert "rationale" in out


def test_plan_with_criteria():
    out = run(["plan", "--question", "Which architecture to choose?",
               "--options", "microservices,monolith",
               "--criteria", "maintainability,scalability",
               "--project-path", PROJECT])
    assert "matrix" in out
    assert "microservices" in out["matrix"] or "monolith" in out["matrix"]


def test_research_no_add_sources_fast():
    out = run(["research", "--topic", "Python asyncio patterns",
               "--depth", "fast", "--no-add-sources",
               "--project-path", PROJECT])
    assert out["status"] == "ok"
    assert out["add_sources"] is False
    assert out["sources_imported"] == 0
    assert isinstance(out["sources"], list)


def test_research_no_add_sources_deep():
    out = run(["research", "--topic", "REST API design best practices",
               "--depth", "deep", "--no-add-sources",
               "--project-path", PROJECT])
    assert out["status"] == "ok"
    assert len(out.get("report", "")) > 50


def test_add_note():
    out = run(["add", "--note", "Test note from integration test",
               "--title", "Integration Test Note",
               "--project-path", PROJECT])
    assert out["status"] == "ok"
    assert out["type"] == "note"
    assert "id" in out["note"]


def test_add_missing_args_fails():
    run(["add", "--project-path", PROJECT], expect_success=False)


def test_setup_notebook_list():
    """--notebook-list returns table format, cache info and next_step."""
    out = run(["setup", "--notebook-list", "--project-path", PROJECT])
    assert out["action"] == "select_notebook"
    assert "cache" in out
    assert "cached_at" in out["cache"]
    assert isinstance(out["total"], int)
    assert out["total"] > 0
    assert isinstance(out["table"], list)
    first = out["table"][0]
    assert "#" in first
    assert "UUID" in first
    assert "Title" in first
    assert "Sources" in first
    assert "next_step" in out
    assert "hint" in out["next_step"]


def test_setup_notebook_list_refresh():
    """--refresh forces API fetch; cache.cached is False."""
    out = run(["setup", "--notebook-list", "--refresh", "--project-path", PROJECT])
    assert out["action"] == "select_notebook"
    assert out["cache"]["cached"] is False


def test_setup_bare_returns_status():
    """Bare setup returns current binding status without calling API."""
    out = run(["setup", "--project-path", PROJECT])
    assert out["status"] == "ok"
    assert "authenticated" in out
    assert "local_notebook" in out
    assert "global_notebooks" in out
    assert out["next_step"] is None


def test_setup_add_local_notebook():
    """--add-local-notebook binds successfully; output has bound=local and next_step."""
    # Get a real UUID from the list
    list_out = run(["setup", "--notebook-list", "--project-path", PROJECT])
    uuid = list_out["table"][0]["UUID"]

    out = run(["setup", "--add-local-notebook", uuid, "--project-path", PROJECT])
    assert out["status"] == "ok"
    assert out["bound"] == "local"
    assert out["local_notebook"]["id"] == uuid
    assert "next_step" in out
    assert "hint" in out["next_step"]


def test_setup_add_global_notebook():
    """--add-global-notebook appends successfully; output has bound=global and total."""
    list_out = run(["setup", "--notebook-list", "--project-path", PROJECT])
    # Take second notebook if available, else first
    uuid = list_out["table"][1]["UUID"] if len(list_out["table"]) > 1 else list_out["table"][0]["UUID"]

    out = run(["setup", "--add-global-notebook", uuid, "--project-path", PROJECT])
    assert out["status"] == "ok"
    assert out["bound"] == "global"
    assert isinstance(out["global_notebooks_total"], int)
    assert any(nb["id"] == uuid for nb in out["added"])


if __name__ == "__main__":
    tests = [
        test_setup_auth,
        test_ask_scope_auto_format_json,
        test_ask_scope_local_format_json,
        test_ask_format_text,
        test_plan_two_options,
        test_plan_with_criteria,
        test_research_no_add_sources_fast,
        test_research_no_add_sources_deep,
        test_add_note,
        test_add_missing_args_fails,
        test_setup_notebook_list,
        test_setup_notebook_list_refresh,
        test_setup_bare_returns_status,
        test_setup_add_local_notebook,
        test_setup_add_global_notebook,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            print(f"✅ {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"❌ {t.__name__}: {e}")
            failed += 1
    print(f"\n{'='*40}")
    print(f"Passed: {passed}/{len(tests)}  Failed: {failed}/{len(tests)}")
    sys.exit(0 if failed == 0 else 1)
