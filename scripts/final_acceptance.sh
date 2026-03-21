#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/AI_Frontend_IDE"
FRONTEND_DIR="$ROOT_DIR/ai-frontend-ide"

echo "[1/4] Running final backend regression suite..."
PYTHONPATH="$BACKEND_DIR" pytest -q

echo
echo "[2/4] Running formal product guardrails..."
PYTHONPATH="$BACKEND_DIR" pytest -q tests/test_final_product_guards.py

echo
echo "[3/4] Verifying no legacy react-agent runtime remains..."
if grep -RIn --exclude="test_final_product_guards.py" "create_react_agent\|langgraph_create_react_agent" "$BACKEND_DIR/app" "$ROOT_DIR/tests"; then
  echo "Legacy react-agent references were found in the formal product path."
  exit 1
fi

echo
echo "[4/4] Building frontend production bundle..."
(cd "$FRONTEND_DIR" && npm run build)

echo
echo "Final acceptance passed."
