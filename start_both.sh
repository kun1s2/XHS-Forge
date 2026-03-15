#!/usr/bin/env bash
# 【XHS-Forge 前台开发启动脚本】
# 功能：强制清理旧进程 -> 加载最新配置 -> 前台同步启动前后端（Ctrl+C 可停止）

set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/AI_Frontend_IDE"
FRONTEND="$ROOT/ai-frontend-ide"
PID_FILE="$ROOT/.start_both.pid"

echo "🧹 [1/3] 正在清理旧进程与残留变量..."
# 杀死所有相关的 python 和 node/vite 进程，确保端口 8000 和 5173 释放
pkill -f "python run.py" || true
pkill -f "uvicorn app.main:app" || true
pkill -f "vite" || true
[ -f "$PID_FILE" ] && rm "$PID_FILE"

echo "📂 [2/3] 正在加载运行环境..."
if command -v conda &>/dev/null; then
    eval "$(conda shell.bash hook)"
    conda activate LangChainProject || echo "⚠️ 未能激活指定 Conda 环境"
fi

echo "🚀 [3/3] 正在启动 XHS-Forge 锻造炉 (前台模式)..."

# 定义退出函数：当用户按下 Ctrl+C 时，同时杀死前后端子进程
trap "kill 0" EXIT

# 启动后端 (不使用 nohup，直接输出到当前终端)
cd "$BACKEND"
python run.py &

# 启动前端
cd "$FRONTEND"
[ ! -d "node_modules" ] && npm install --silent
npm run dev &

# 等待所有后台任务结束
wait
