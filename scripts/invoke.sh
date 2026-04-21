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
REQUIREMENTS="$SKILL_DIR/requirements.txt"

if [ ! -f "$PYTHON" ]; then
  echo "⏳ Setting up nlm environment (first run)..." >&2
  python3 -m venv "$SKILL_DIR/.venv" >&2 || { echo "❌ python3 -m venv failed" >&2; exit 1; }
  "$SKILL_DIR/.venv/bin/pip" install --quiet -r "$REQUIREMENTS" >&2 \
    || { echo "❌ pip install failed — check your internet connection" >&2; exit 1; }
  echo "✅ Environment ready." >&2
fi

exec "$PYTHON" "$SKILL_DIR/scripts/nlm.py" "$@"
