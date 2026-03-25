#!/usr/bin/env bash
# 停止由 start_both_detached.sh 启动的后端与前端进程
# 用法：./stop_both.sh

ROOT="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$ROOT/.start_both.pid"

kill_matching() {
  local pattern="$1"
  pkill -f "$pattern" 2>/dev/null || true
}

if [ ! -f "$PID_FILE" ]; then
  echo "No PID file found. Nothing to stop."
  exit 0
fi

while read -r pid; do
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    echo "Stopped PID $pid"
  fi
done < "$PID_FILE"
rm -f "$PID_FILE"

kill_matching "python run.py"
kill_matching "uvicorn app.main:app"
kill_matching "uvicorn AI_Frontend_IDE.app.main:app"
kill_matching "watchfiles"
kill_matching "AI_Frontend_IDE.app.main:app"
kill_matching "vite"
kill_matching "node .*vite"

echo "Done."
