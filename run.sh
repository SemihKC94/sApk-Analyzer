#!/usr/bin/env bash
# sApkAnalyzer Launcher for macOS and Linux

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
else
    echo "Error: Python not found! Please install Python 3."
    exit 1
fi

"$PYTHON_CMD" main.py "$@"
