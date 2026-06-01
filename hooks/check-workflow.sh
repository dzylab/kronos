#!/usr/bin/env bash
# KRONOS Workflow Engine — PreToolUse hook (bash wrapper).
# Delegates the logic to check-workflow.py (Python is more reliable cross-platform).
#
# Usage:
#   - settings.json registers this file as the command
#   - or self-test: bash check-workflow.sh --self-test

DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$DIR/check-workflow.py"

# Windows/MSYS: PYTHONHOME/PYTHONPATH left over from old installs may be set, and
# the conflict breaks startup with "ModuleNotFoundError: No module named 'encodings'".
# Clear those env vars so python finds its own stdlib.
unset PYTHONHOME
unset PYTHONPATH

# UTF-8 mode: otherwise Path() for non-ASCII paths may return exists=False
# (mbcs/cp1251 vs filesystem UTF-8 mismatch on Windows).
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

# Pick a Python: try standard paths first, then PATH
PY=""
for candidate in \
    "/c/Program Files/Python312/python.exe" \
    "/c/Program Files/Python311/python.exe" \
    "/c/Program Files/Python310/python.exe" \
    "/c/Users/$USER/AppData/Local/Programs/Python/Python312/python.exe" \
    "/c/Users/$USER/AppData/Local/Programs/Python/Python311/python.exe" \
    "python3" "python"; do
    if [ -x "$candidate" ] 2>/dev/null || command -v "$candidate" >/dev/null 2>&1; then
        PY="$candidate"
        break
    fi
done

if [ -z "$PY" ]; then
    echo "[kronos] FATAL: python not found in PATH or standard locations" >&2
    exit 1
fi

exec "$PY" "$SCRIPT" "$@"
