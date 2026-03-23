#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[1/5] Running final acceptance..."
bash "$ROOT_DIR/scripts/final_acceptance.sh"

echo
echo "[2/5] Running runtime/workspace integration audit..."
cd "$ROOT_DIR"
pytest -q \
  tests/test_e2e_smoke.py \
  tests/test_workspace_assets_api.py \
  tests/test_workspace_api.py \
  tests/test_workspace_showcase_api.py \
  tests/test_chat_ws_integration.py \
  tests/test_ws_probe.py

echo
echo "[3/5] Running generation and editor audit..."
pytest -q \
  tests/test_generation_smoke.py \
  tests/test_note_editor_v2.py \
  tests/test_patch_node.py \
  tests/test_architecture_v2.py

echo
echo "[4/5] Running RAG / trends / cache audit..."
pytest -q \
  tests/test_rag_pipeline.py \
  tests/test_trend_pipeline.py \
  tests/test_enrichment_agent.py \
  tests/test_enrichment_integration.py

echo
echo "[5/5] Running frontend visual audit..."
cd "$ROOT_DIR/ai-frontend-ide"
npm run visual:test

echo
echo "Full system audit passed."
