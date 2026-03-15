#!/usr/bin/env bash
# 停止由 start_both_detached.sh 启动的后端与前端进程
# 用法：./stop_both.sh

ROOT="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$ROOT/.start_both.pid"

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
echo "Done."
