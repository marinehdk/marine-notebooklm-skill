#!/usr/bin/env bash
# Resolve symlinks to find the real skill directory
SOURCE="${BASH_SOURCE[0]}"
while [ -L "$SOURCE" ]; do
  DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
  SOURCE="$(readlink "$SOURCE")"
  [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
SKILL_DIR="$(cd -P "$(dirname "$SOURCE")/.." && pwd)"

PYTHON="$SKILL_DIR/.venv/bin/python"

if [ ! -f "$PYTHON" ]; then
  echo "❌ venv not found. Run: cd $SKILL_DIR && python3 -m venv .venv && .venv/bin/pip install notebooklm" >&2
  exit 1
fi

exec "$PYTHON" "$SKILL_DIR/scripts/nlm.py" "$@"
