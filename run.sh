#!/usr/bin/env bash
# Start Margin in this terminal (Linux / macOS). Same as: python3 start.py
# The first run sets everything up automatically. Options: see start.py (--app, --install, --quit).
cd "$(dirname "$0")" || exit 1
exec python3 start.py "$@"
