#!/usr/bin/env bash
# 【XHS-Forge 核心启动脚本 - 后台版】
# 功能：强制清理旧进程 -> 加载最新配置 -> 后台启动前后端

set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/AI_Frontend_IDE"
FRONTEND="$ROOT/ai-frontend-ide"
PID_FILE="$ROOT/.start_both.pid"
LOG_DIR="$ROOT/logs"

kill_matching() {
  local pattern="$1"
  pkill -f "$pattern" 2>/dev/null || true
}

mkdir -p "$LOG_DIR"

echo "🧹 [1/3] 正在强制清理旧进程，防止端口占用与变量残留..."
# 杀死所有相关的 python 和 node/vite 进程
kill_matching "python run.py"
kill_matching "uvicorn app.main:app"
kill_matching "uvicorn AI_Frontend_IDE.app.main:app"
kill_matching "watchfiles"
kill_matching "AI_Frontend_IDE.app.main:app"
kill_matching "vite"
kill_matching "node .*vite"
# 如果有 PID 文件，也尝试清理
if [ -f "$PID_FILE" ]; then
  while read pid; do
    kill -9 "$pid" 2>/dev/null || true
  done < "$PID_FILE"
  rm "$PID_FILE"
fi

echo "📂 [2/3] 正在准备运行环境..."
# 尝试激活 Conda 环境 (LangChainProject)
if command -v conda &>/dev/null; then
    # 尝试多种方式激活，适配不同的 shell 配置
    eval "$(conda shell.bash hook)"
    conda activate LangChainProject || echo "⚠️ 未能激活指定 Conda 环境，将尝试使用系统 Python"
fi

echo "🚀 [3/3] 正在后台启动 XHS-Forge 服务..."
echo "ℹ️ 如果刚升级过运行时/序列化协议，建议先执行: bash scripts/reset_project_state.sh --yes"

# 启动后端
cd "$BACKEND"
# 强制使用最新的环境变量运行
nohup env XHS_FORGE_RELOAD=false python run.py >> "$LOG_DIR/backend.log" 2>&1 &
echo $! >> "$PID_FILE"

# 启动前端
cd "$FRONTEND"
[ ! -d "node_modules" ] && npm install --silent
nohup npm run dev >> "$LOG_DIR/frontend.log" 2>&1 &
echo $! >> "$PID_FILE"

cd "$ROOT"
echo "------------------------------------------------"
echo "✅ 服务已成功在后台锻造完成！"
echo "🌐 前端预览: http://localhost:5173"
echo "📝 后端 API: http://localhost:8000"
echo "📜 日志查看: tail -f logs/backend.log"
echo "🛑 停止服务: ./stop_both.sh"
echo "------------------------------------------------"
