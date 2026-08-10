#!/usr/bin/env bash
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

# A broad `python3` fallback is unsafe here: the frozen result contract
# requires Python 3.11.x, and 3.12/3.13 must fail before creating a venv.
PYTHON_BIN="${PYTHON_BIN:-python3.11}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "ERROR: Python 3.11.x was not found via '$PYTHON_BIN'." >&2
  echo "Install it explicitly, for example: uv python install 3.11" >&2
  echo "Then retry with: PYTHON_BIN=\"\$(uv python find 3.11)\" bash setup.sh" >&2
  exit 2
fi
PYTHON_VERSION="$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")' 2>/dev/null || true)"
case "$PYTHON_VERSION" in
  3.11.*) ;;
  *)
    echo "ERROR: Python 3.11.x is required; '$PYTHON_BIN' reports '${PYTHON_VERSION:-unusable interpreter}'." >&2
    echo "Install it explicitly, for example: uv python install 3.11" >&2
    exit 2
    ;;
esac

VENV_DIR="$ROOT_DIR/.venv"
if [ -x "$VENV_DIR/bin/python" ]; then
  VENV_VERSION="$("$VENV_DIR/bin/python" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")' 2>/dev/null || true)"
  case "$VENV_VERSION" in
    3.11.*) ;;
    *)
      echo "ERROR: existing $VENV_DIR uses '${VENV_VERSION:-unusable interpreter}', not Python 3.11.x." >&2
      echo "Remove that venv deliberately, then rerun this setup command." >&2
      exit 2
      ;;
  esac
else
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi
VENV_PYTHON="$ROOT_DIR/.venv/bin/python"
"$VENV_PYTHON" -m pip install --disable-pip-version-check --require-hashes --no-deps -r "$ROOT_DIR/requirements-lock.txt"
exec "$VENV_PYTHON" "$ROOT_DIR/verify_setup.py"
