"""Shared progress reporting for nlm CLI commands.

All output goes to stderr so it doesn't interfere with JSON stdout.
Format: ⏳ [step/total] message  /  ✅ [step/total] message (done)
"""
from __future__ import annotations
import sys


def step(current: int, total: int, msg: str) -> None:
    """Print an in-progress step."""
    print(f"⏳ [{current}/{total}] {msg}", file=sys.stderr, flush=True)


def done(current: int, total: int, msg: str) -> None:
    """Print a completed step."""
    print(f"✅ [{current}/{total}] {msg}", file=sys.stderr, flush=True)


def warn(msg: str) -> None:
    """Print a warning line."""
    print(f"⚠️  {msg}", file=sys.stderr, flush=True)


def info(msg: str) -> None:
    """Print a plain info line (no step counter)."""
    print(f"   {msg}", file=sys.stderr, flush=True)
