#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python -m venv .venv

if [[ -x ".venv/bin/python" ]]; then
  PYTHON_BIN=".venv/bin/python"
else
  PYTHON_BIN=".venv/Scripts/python.exe"
fi

"$PYTHON_BIN" -m pip install --upgrade pip
"$PYTHON_BIN" -m pip install -r requirements/lock.txt
"$PYTHON_BIN" -m pip install pre-commit
"$PYTHON_BIN" -m pre_commit install

echo "Local setup completed."
echo "Run app with: $PYTHON_BIN -m streamlit run src/app.py"
