# app/main.py
import warnings
warnings.filterwarnings("ignore", message=".*Pydantic serializer warnings.*")

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.persistence import generate_checkpointer, generate_store,generate_vector_store
from app.agents.graph import compile_my_graph
from app.services.cache_service import sync_risk_words_from_cloud, scheduled_risk_sync_task

# 导入拆分好的路由
from app.api.workspace import router as workspace_router
from app.api.chat import router as chat_router
from app.api.upload import router as upload_router

from app.services.trend_pipeline import trend_pipeline
from app.services.knowledge_hub import knowledge_hub_service

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ================= 启动阶段 (Startup) =================
    print("🚀 [System] 正在初始化系统组件...")
    
    # 1. 启动哨兵热点预热流水线
    await trend_pipeline.start_background_task()
    
    # 2. 项目启动时，在后台拉取一次最新词库（不阻塞主流程）
    asyncio.create_task(sync_risk_words_from_cloud())
    
    # 2. 启动后台守护协程，执行定时同步 (已改为每天凌晨 02:00)
    sync_task = asyncio.create_task(scheduled_risk_sync_task())
    print("🛡️ [System] 风控词库云端定时同步守护进程已启动，将在每天凌晨 02:00 执行。")

    # 使用 async with 嵌套管理多个异步上下文
    async with generate_checkpointer() as checkpointer, \
               generate_store() as store, \
               generate_vector_store() as vector_store: # <--- 你的自定义上下文
        
        # 挂载图引擎
        app.state.agent = compile_my_graph(checkpointer, store)
        app.state.store = store
        knowledge_hub_service.bind_store(store)
        # 挂载全局唯一的向量数据库实例
        app.state.vector_store = vector_store 
        
        print("✅ Backend Engine & PGVector Started Successfully")
        yield

    # ================= 关闭阶段 (Shutdown) =================
    print("🛑 [System] 正在优雅关闭系统组件...")
    knowledge_hub_service.bind_store(None)
    sync_task.cancel() # 停止后台同步任务
    try:
        await sync_task
    except asyncio.CancelledError:
        print("🛡️ [System] 定时同步守护进程已安全终止。")

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
