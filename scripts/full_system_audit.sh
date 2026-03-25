#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[1/5] Running final acceptance..."
bash "$ROOT_DIR/scripts/final_acceptance.sh"

echo
echo "[2/5] Running runtime/workspace integration audit..."
cd "$ROOT_DIR"
pytest -q \
  tests/test_workspace_assets_api.py \
  tests/test_workspace_api.py \
  tests/test_workspace_showcase_api.py \
  tests/test_chat_ws_integration.py \
  tests/test_ws_probe.py

echo
echo "[3/5] Running supervisor / artifact / revision audit..."
pytest -q \
  tests/test_agent_runtime.py \
  tests/test_artifact_revision_services.py \
  tests/test_digital_purchase_runtime.py \
  tests/test_final_product_guards.py

echo
echo "[4/5] Running RAG / trends / cache audit..."
pytest -q \
  tests/test_rag_pipeline.py \
  tests/test_trend_pipeline.py \
  tests/test_knowledge_hub.py \
  tests/test_skill_registry.py

echo
echo "[5/5] Running frontend visual audit..."
cd "$ROOT_DIR/ai-frontend-ide"
npm run visual:test

echo
echo "Full system audit passed."
