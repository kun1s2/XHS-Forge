import logging
import json
from typing import List, Dict, Any
from sqlalchemy import text
from app.core.config import settings
from app.core.persistence import get_embedding
from sqlalchemy.ext.asyncio import create_async_engine

logger = logging.getLogger(__name__)


def _to_asyncpg_url(url: str) -> str:
    """将任意 PostgreSQL URL 转为 asyncpg 驱动格式，供 create_async_engine 使用。"""
    for prefix in ("postgresql+psycopg2://", "postgresql+psycopg://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+asyncpg://" + url[len(prefix):]
    return url


_engine = None


def _get_engine():
    global _engine
    if _engine is not None:
        return _engine
    database_url = str(settings.PGVector_URL or "").strip()
    if not database_url:
        return None
    _engine = create_async_engine(_to_asyncpg_url(database_url))
    return _engine

async def hybrid_search_rrf(
    query: str, 
    k: int = 3, 
    rrf_k: int = 60
) -> List[Dict[str, Any]]:
    """
    【Postgres 混合召回引擎】：结合向量相似度与全文检索，并使用 RRF 算法融合评分。
    """
    # 1. 获取向量表示
    embeddings = get_embedding()
    query_vector = await embeddings.aembed_query(query)
    
    # 2. 构造 SQL
    # langchain_postgres 默认表名: langchain_pg_embedding, langchain_pg_collection
    # 默认列名: document (文本), cmetadata (元数据), embedding (向量)
    sql = text("""
    WITH vector_search AS (
        SELECT 
            uuid, 
            document, 
            cmetadata,
            1 - (embedding <=> :vector::vector) as similarity,
            row_number() OVER (ORDER BY embedding <=> :vector::vector) as rank
        FROM langchain_pg_embedding
        WHERE collection_id = (SELECT uuid FROM langchain_pg_collection WHERE name = 'app' LIMIT 1)
        LIMIT 20
    ),
    text_search AS (
        SELECT 
            uuid,
            ts_rank_cd(to_tsvector('chinese', document), plainto_tsquery('chinese', :query)) as text_score,
            row_number() OVER (ORDER BY ts_rank_cd(to_tsvector('chinese', document), plainto_tsquery('chinese', :query)) DESC) as rank
        FROM langchain_pg_embedding
        WHERE collection_id = (SELECT uuid FROM langchain_pg_collection WHERE name = 'app' LIMIT 1)
        AND to_tsvector('chinese', document) @@ plainto_tsquery('chinese', :query)
        LIMIT 20
    )
    SELECT 
        COALESCE(v.uuid, t.uuid) as uuid,
        COALESCE(v.document, (SELECT document FROM langchain_pg_embedding WHERE uuid = t.uuid)) as content,
        COALESCE(v.cmetadata, (SELECT cmetadata FROM langchain_pg_embedding WHERE uuid = t.uuid)) as metadata,
        (COALESCE(1.0 / (:rrf_k + v.rank), 0.0) + COALESCE(1.0 / (:rrf_k + t.rank), 0.0)) as rrf_score
    FROM vector_search v
    FULL OUTER JOIN text_search t ON v.uuid = t.uuid
    ORDER BY rrf_score DESC
    LIMIT :limit;
    """)

    try:
        engine = _get_engine()
        if engine is None:
            logger.info("混合召回已跳过：PGVector_URL 未配置。")
            return []
        async with engine.connect() as conn:
            # Postgres 的 vector 类型需要特殊处理，这里将 list 转为字符串格式 '[...]'
            vector_str = "[" + ",".join(map(str, query_vector)) + "]"
            
            result = await conn.execute(sql, {
                "vector": vector_str, 
                "query": query, 
                "rrf_k": rrf_k, 
                "limit": k
            })
            
            final_results = []
            for row in result:
                final_results.append({
                    "page_content": row.content,
                    "metadata": row.metadata,
                    "score": row.rrf_score
                })
            
            if final_results:
                print(f"🧬 [混合召回] 命中 {len(final_results)} 条结果，RRF 最高分: {final_results[0]['score']:.4f}")
            return final_results
    except Exception as e:
        logger.error(f"混合召回失败: {e}")
        # 降级处理：如果混合召回失败（如没装 zhparser 或向量插件），返回空
        return []
