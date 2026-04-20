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


def test_setup_list_notebooks():
    out = run(["setup", "--project-path", "/tmp/nlm-fresh-test"])
    assert "action" in out
    assert out["action"] == "select_notebook"
    assert len(out["notebooks"]) > 0


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
        test_setup_list_notebooks,
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
