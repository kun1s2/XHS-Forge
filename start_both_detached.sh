#!/usr/bin/env bash
# 后台同时启动前后端（适合云服务器，关闭终端后仍运行）
# 用法：./start_both_detached.sh
# 停止：./stop_both.sh

set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/AI_Frontend_IDE"
FRONTEND="$ROOT/ai-frontend-ide"
PID_FILE="$ROOT/.start_both.pid"
LOG_DIR="$ROOT/logs"

mkdir -p "$LOG_DIR"

# 可选：激活虚拟环境
if [ -d "$ROOT/.venv" ] && [ -f "$ROOT/.venv/bin/activate" ]; then
  source "$ROOT/.venv/bin/activate"
elif [ -d "$BACKEND/.venv" ] && [ -f "$BACKEND/.venv/bin/activate" ]; then
  source "$BACKEND/.venv/bin/activate"
fi

PYTHON="${PYTHON:-python3}"
command -v "$PYTHON" &>/dev/null || PYTHON=python

# 若已有 PID 文件，先尝试停止旧进程
if [ -f "$PID_FILE" ]; then
  echo "Found existing PID file. Run ./stop_both.sh first, or remove $PID_FILE"
  exit 1
fi

echo "Starting backend and frontend in background..."
cd "$BACKEND"
nohup $PYTHON run.py >> "$LOG_DIR/backend.log" 2>&1 &
echo $! >> "$PID_FILE"
cd "$FRONTEND"
[ ! -d "node_modules" ] && npm install
nohup npm run dev >> "$LOG_DIR/frontend.log" 2>&1 &
echo $! >> "$PID_FILE"
cd "$ROOT"

echo "Backend: http://127.0.0.1:8000 (log: $LOG_DIR/backend.log)"
echo "Frontend: http://localhost:5173 (log: $LOG_DIR/frontend.log)"
echo "To stop: ./stop_both.sh"
echo "PIDs saved in $PID_FILE"
