# tests/test_cmd_add_target.py
"""Verify cmd_add --target argument parsing."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


def _parse_add_args(args: list[str]):
    import argparse
    parser = argparse.ArgumentParser(prog="nlm add")
    parser.add_argument("--url")
    parser.add_argument("--note")
    parser.add_argument("--title", default="Note")
    parser.add_argument(
        "--target", default="local",
        help="local (default), synthesis, or domain:<key>",
    )
    parser.add_argument("--project-path", default=".")
    return parser.parse_args(args)


def test_default_target_is_local():
    parsed = _parse_add_args(["--url", "https://example.com"])
    assert parsed.target == "local"


def test_target_synthesis():
    parsed = _parse_add_args(["--note", "text", "--target", "synthesis"])
    assert parsed.target == "synthesis"


def test_target_domain():
    parsed = _parse_add_args(["--url", "https://x.com", "--target", "domain:colav"])
    assert parsed.target == "domain:colav"


def test_target_domain_with_key():
    parsed = _parse_add_args(["--url", "https://x.com", "--target", "domain:maritime_regulations"])
    assert parsed.target == "domain:maritime_regulations"
