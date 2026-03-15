#!/usr/bin/env bash
# 同时启动后端 (AI_Frontend_IDE) 与前端 (ai-frontend-ide) — Linux / macOS
# 用法：./start_both.sh  或  bash start_both.sh

set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/AI_Frontend_IDE"
FRONTEND="$ROOT/ai-frontend-ide"

# 可选：若项目根目录或后端目录下有虚拟环境则自动激活
if [ -d "$ROOT/.venv" ] && [ -f "$ROOT/.venv/bin/activate" ]; then
  source "$ROOT/.venv/bin/activate"
elif [ -d "$BACKEND/.venv" ] && [ -f "$BACKEND/.venv/bin/activate" ]; then
  source "$BACKEND/.venv/bin/activate"
fi

PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" &>/dev/null; then
  PYTHON=python
fi

echo "Backend: $BACKEND (port 8000)"
echo "Frontend: $FRONTEND (port 5173)"
echo ""

# 启动后端（后台），并记录 PID
cd "$BACKEND"
$PYTHON run.py &
BACKEND_PID=$!
cd "$ROOT"

# 退出时清理后端进程
cleanup() {
  echo ""
  echo "Stopping backend (PID $BACKEND_PID)..."
  kill "$BACKEND_PID" 2>/dev/null || true
  exit 0
}
trap cleanup SIGINT SIGTERM EXIT

sleep 2

# 启动前端（前台，占用当前终端）
cd "$FRONTEND"
if [ ! -d "node_modules" ]; then
  echo "Installing frontend dependencies..."
  npm install
fi
npm run dev
