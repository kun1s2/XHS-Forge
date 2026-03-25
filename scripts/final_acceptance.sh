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
echo "[3/4] Verifying no deprecated runtime vocabulary remains in the formal path..."
if grep -RIn \
  --exclude="test_final_product_guards.py" \
  --exclude-dir="__pycache__" \
  "UIProjectState\|critique_action\|_run_graph_loop\|compile_my_graph\|review_worker\|asset_worker\|node_prompts\|currentNode" \
  "$BACKEND_DIR/app" "$ROOT_DIR/ai-frontend-ide/src" "$ROOT_DIR/tests"; then
  echo "Deprecated runtime vocabulary was found in the formal product path."
  exit 1
fi

echo
echo "[4/4] Building frontend production bundle..."
(cd "$FRONTEND_DIR" && npm run build)

echo
echo "Final acceptance passed."
