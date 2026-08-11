#!/usr/bin/env bash
set -eu

# Recovery commands are forwarded unchanged on POSIX and Windows:
# status, restore --checkpoint <role>, and reset-policy.
ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if [ -x "$ROOT_DIR/.venv/bin/python" ]; then
  PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi
exec "$PYTHON_BIN" "$ROOT_DIR/run_lab.py" "$@"
