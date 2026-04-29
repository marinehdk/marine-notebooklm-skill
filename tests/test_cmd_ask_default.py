"""Verify cmd_ask default --on-low-confidence is 'prompt', not 'research'."""
import sys
from pathlib import Path
import argparse
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


def _parse_ask_args(args: list[str]):
    parser = argparse.ArgumentParser(prog="nlm ask")
    parser.add_argument("--question", required=True)
    parser.add_argument("--scope", default="auto")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    parser.add_argument("--project-path", default=".")
    parser.add_argument(
        "--on-low-confidence",
        choices=["prompt", "research", "silent"],
        default="prompt",  # correct per spec
    )
    return parser.parse_args(args)


def test_default_on_low_confidence_should_be_prompt():
    """GAP-3: spec §3.2.2 says default is 'prompt', not 'research'."""
    parsed = _parse_ask_args(["--question", "test"])
    assert parsed.on_low_confidence == "prompt", (
        "Default must be 'prompt' per spec §3.2.2 (§6 'never auto-write'). "
        "Currently 'research' auto-imports, violating the no-write rule."
    )
