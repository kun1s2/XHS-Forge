#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/AI_Frontend_IDE"
ENV_FILE="$BACKEND_DIR/.env"
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python3"
fi

usage() {
  cat <<'EOF'
用法:
  bash scripts/reset_project_state.sh --yes [--skip-seed] [--skip-logs]

作用:
  1. 清空 Redis 当前库中的热点/缓存数据
  2. 清空 PostgreSQL public schema（包括 LangGraph checkpoints、store、PGVector 表）
  3. 重新创建当前项目运行所需的 store/checkpointer/vector store 表
  4. 默认重新灌入一份基础向量知识（seed_knowledge.py）

参数:
  --yes         必填，确认执行破坏性重置
  --skip-seed   只重建空表，不灌入示例知识
  --skip-logs   不清空本地 log 目录
  --help        查看说明

说明:
  - 这是“全量清空 + 当前项目重新初始化”脚本，不保留旧 checkpoint/旧缓存。
  - 如果检测到 Docker 容器 xhs-postgres / xhs-redis / xhs-backend 正在运行，会优先走 Docker。
  - 若未检测到 Docker，会回退到本地 psql / redis-cli / Python 环境。
EOF
}

CONFIRM="false"
WITH_SEED="true"
CLEAR_LOGS="true"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --yes)
      CONFIRM="true"
      shift
      ;;
    --skip-seed)
      WITH_SEED="false"
      shift
      ;;
    --skip-logs)
      CLEAR_LOGS="false"
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "未知参数: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ "$CONFIRM" != "true" ]]; then
  echo "这是破坏性重置脚本，请显式传入 --yes。" >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "未找到环境文件: $ENV_FILE" >&2
  exit 1
fi

read_config_json() {
  cd "$ROOT_DIR"
  "$PYTHON_BIN" - <<'PY'
import json
import sys
from pathlib import Path

root = Path.cwd()
sys.path.append(str(root / "AI_Frontend_IDE"))

from app.core.config import settings

print(json.dumps({
    "POSTGRES_URL": settings.POSTGRES_URL,
    "REDIS_URL": settings.REDIS_URL,
}))
PY
}

CONFIG_JSON="$(read_config_json)"
POSTGRES_URL="$("$PYTHON_BIN" -c 'import json,sys; print(json.load(sys.stdin)["POSTGRES_URL"])' <<<"$CONFIG_JSON")"
REDIS_URL="$("$PYTHON_BIN" -c 'import json,sys; print(json.load(sys.stdin)["REDIS_URL"])' <<<"$CONFIG_JSON")"

has_docker() {
  command -v docker >/dev/null 2>&1
}

container_running() {
  local name="$1"
  docker ps --format '{{.Names}}' | grep -Fxq "$name"
}

run_postgres_reset_docker() {
  echo "🧨 通过 Docker 重置 PostgreSQL public schema..."
  docker exec -i xhs-postgres psql -U postgres -d LangChainProject -v ON_ERROR_STOP=1 <<'SQL'
DROP SCHEMA IF EXISTS public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO postgres;
GRANT ALL ON SCHEMA public TO public;
CREATE EXTENSION IF NOT EXISTS vector;
SQL
}

run_redis_reset_docker() {
  echo "🧨 通过 Docker 清空 Redis 当前库..."
  docker exec -i xhs-redis redis-cli -a qq15160160 FLUSHDB >/dev/null
}

run_backend_init_docker() {
  echo "🏗️ 通过 Docker 重建 store/checkpointer/vector store..."
  docker exec -i xhs-backend python - <<'PY'
import asyncio
from app.core.persistence import generate_store, generate_checkpointer, generate_vector_store

async def main():
    async with generate_store():
        pass
    async with generate_checkpointer():
        pass
    async with generate_vector_store():
        pass

asyncio.run(main())
PY
}

run_seed_docker() {
  echo "🌱 通过 Docker 灌入基础知识样本..."
  docker exec -i xhs-backend python app/scripts/seed_knowledge.py
}

run_postgres_reset_local() {
  echo "🧨 使用本地 psql 重置 PostgreSQL public schema..."
  psql "$POSTGRES_URL" -v ON_ERROR_STOP=1 <<'SQL'
DROP SCHEMA IF EXISTS public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO CURRENT_USER;
GRANT ALL ON SCHEMA public TO public;
CREATE EXTENSION IF NOT EXISTS vector;
SQL
}

run_redis_reset_local() {
  echo "🧨 使用本地 redis-cli 清空 Redis 当前库..."
  "$PYTHON_BIN" - "$REDIS_URL" <<'PY'
import sys
from urllib.parse import urlparse
from subprocess import run

redis_url = sys.argv[1]
parsed = urlparse(redis_url)
host = parsed.hostname or "127.0.0.1"
port = str(parsed.port or 6379)
password = parsed.password or ""
db = (parsed.path or "/0").lstrip("/") or "0"

cmd = ["redis-cli", "-h", host, "-p", port, "-n", db]
if password:
    cmd.extend(["-a", password])
cmd.append("FLUSHDB")
run(cmd, check=True)
PY
}

run_backend_init_local() {
  echo "🏗️ 使用本地 Python 重建 store/checkpointer/vector store..."
  (
    cd "$BACKEND_DIR"
    "$PYTHON_BIN" - <<'PY'
import asyncio
from app.core.persistence import generate_store, generate_checkpointer, generate_vector_store

async def main():
    async with generate_store():
        pass
    async with generate_checkpointer():
        pass
    async with generate_vector_store():
        pass

asyncio.run(main())
PY
  )
}

run_seed_local() {
  echo "🌱 使用本地 Python 灌入基础知识样本..."
  (
    cd "$BACKEND_DIR"
    "$PYTHON_BIN" app/scripts/seed_knowledge.py
  )
}

clear_logs_if_needed() {
  if [[ "$CLEAR_LOGS" != "true" ]]; then
    return
  fi
  echo "🧹 清理本地运行日志..."
  rm -rf "$BACKEND_DIR/log"/*
}

echo "== XHS-Forge 全量重置 =="
echo "ROOT_DIR: $ROOT_DIR"
echo "POSTGRES_URL: $POSTGRES_URL"
echo "REDIS_URL: $REDIS_URL"

USE_DOCKER="false"
if has_docker && container_running xhs-postgres && container_running xhs-redis; then
  USE_DOCKER="true"
fi

if [[ "$USE_DOCKER" == "true" ]]; then
  echo "🐳 检测到 Docker 运行中的 postgres/redis，优先使用容器内重置。"
  run_redis_reset_docker
  run_postgres_reset_docker
  if container_running xhs-backend; then
    run_backend_init_docker
    if [[ "$WITH_SEED" == "true" ]]; then
      run_seed_docker
    fi
  else
    echo "⚠️ 未检测到 xhs-backend，改用本地 Python 执行初始化。"
    run_backend_init_local
    if [[ "$WITH_SEED" == "true" ]]; then
      run_seed_local
    fi
  fi
else
  echo "🖥️ 未检测到 Docker 容器，使用本地 psql / redis-cli / Python 执行重置。"
  run_redis_reset_local
  run_postgres_reset_local
  run_backend_init_local
  if [[ "$WITH_SEED" == "true" ]]; then
    run_seed_local
  fi
fi

clear_logs_if_needed

echo
echo "✅ 重置完成。"
if [[ "$WITH_SEED" == "true" ]]; then
  echo "当前状态：旧 checkpoint/旧缓存/旧向量数据已清空，基础知识样本已重新灌入。"
else
  echo "当前状态：旧 checkpoint/旧缓存/旧向量数据已清空，当前数据库为空壳。"
fi
