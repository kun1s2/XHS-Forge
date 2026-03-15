import contextlib
from langgraph.store.postgres import AsyncPostgresStore
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from app.core.config import settings
from langchain_postgres import PGVector
from langchain_community.embeddings import ZhipuAIEmbeddings

# 异步 Store 工厂 (保持不变)
@contextlib.asynccontextmanager
async def generate_store():
    async with AsyncPostgresStore.from_conn_string(settings.POSTGRES_URL) as store:
        await store.setup()
        yield store

# 异步 Checkpointer 工厂 (保持不变)
@contextlib.asynccontextmanager
async def generate_checkpointer():
    async with AsyncPostgresSaver.from_conn_string(settings.POSTGRES_URL) as saver:
        await saver.setup()
        yield saver

def get_embedding():
    """使用智谱官方 Embedding 模型构建向量库"""
    return ZhipuAIEmbeddings(
        api_key=settings.ZHI_PU_API_KEY,
        model="embedding-3"
    )

@contextlib.asynccontextmanager
async def generate_vector_store():
    store = PGVector(
        connection=settings.PGVector_URL, # 例如 postgresql+psycopg://...
        embeddings=get_embedding(),
        collection_name='app',
        use_jsonb=True,
        async_mode=True,  # 开启全异步驱动
    )
    
    # 【新增优化】：在引擎启动时主动建表（如果表不存在）。
    # 这对齐了上面 await store.setup() 的行为，防止首次查询报错。
    await store.acreate_tables_if_not_exists()
    
    print(f"✅ PGVector store initialized in async mode for collection 'app'.")

    try:
        yield store
    finally:
        # 注意：由于直接传入 connection 字符串，langchain_postgres 会在内部自己管理 engine 释放。
        print("🔌 PGVector store context exited.")