#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "Starting Behave AI Laboratory..."

if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: Python 3 is required but was not found."
    exit 1
fi

if [ ! -d ".venv" ]; then
    echo "Preparing Behave for first launch..."
    python3 -m venv .venv
fi

PYTHON=".venv/bin/python"
"$PYTHON" -m pip install -q -r requirements.txt
exec "$PYTHON" launch_behave.py
