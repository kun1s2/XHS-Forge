# run.py — FastAPI 启动入口（应用：src.agent.webapp）
# 用法：python run.py
# 端口与 config.SERVER_PORT 一致，默认 8000，与前端 VITE_API_BASE_URL 对齐
import asyncio
import selectors
import sys
import os

import uvicorn

# 项目根目录与 src 加入 Python 路径
_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _root)


from app.core.config import settings


async def _serve():
    config = uvicorn.Config(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    # Windows 上 psycopg 异步驱动必须运行在 SelectorEventLoop 中
    if sys.platform == "win32":
        loop_factory = lambda: asyncio.SelectorEventLoop(selectors.SelectSelector())
        asyncio.run(_serve(), loop_factory=loop_factory)
    else:
        asyncio.run(_serve())
