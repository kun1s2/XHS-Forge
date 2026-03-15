# app/main.py
import warnings
warnings.filterwarnings("ignore", message=".*Pydantic serializer warnings.*")

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.persistence import generate_checkpointer, generate_store,generate_vector_store
from app.agents.graph import compile_my_graph

# 导入拆分好的路由
from app.api.workspace import router as workspace_router
from app.api.chat import router as chat_router
from app.api.upload import router as upload_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 使用 async with 嵌套管理多个异步上下文
    async with generate_checkpointer() as checkpointer, \
               generate_store() as store, \
               generate_vector_store() as vector_store: # <--- 你的自定义上下文
        
        # 挂载图引擎
        app.state.agent = compile_my_graph(checkpointer, store)
        # 挂载全局唯一的向量数据库实例
        app.state.vector_store = vector_store 
        
        print("✅ Backend Engine & PGVector Started Successfully")
        yield

app = FastAPI(title="AI Frontend IDE Backend", lifespan=lifespan)

# 允许前端开发服务器跨域（Vite 默认 localhost:5173）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载路由（测试与前端使用 ws://host/ws/chat/{thread_id}；上传图片 POST /upload/image、/upload/images）
app.include_router(workspace_router)
app.include_router(chat_router, prefix="/ws")
app.include_router(upload_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.API_HOST, port=settings.API_PORT, reload=True)