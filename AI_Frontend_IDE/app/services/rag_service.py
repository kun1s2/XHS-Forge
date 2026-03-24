import logging
from typing import Any, Dict, List
from app.core.persistence import generate_vector_store
from app.core.config import settings
from app.core.llm_factory import create_llm
from pydantic import BaseModel, Field
from app.services.vector_db import hybrid_search_rrf

logger = logging.getLogger(__name__)

class QueryFilter(BaseModel):
    filter_dict: Dict = Field(default_factory=dict, description="针对 metadata 的过滤字典，如 {'price': {'$lt': 500}}")
    refined_query: str = Field(description="优化后的纯文本查询词")

async def _parse_self_query(query: str) -> QueryFilter:
    """
    【Self-Query 解析器】：利用 LLM 将自然语言解析为结构化过滤条件。
    """
    llm = create_llm(
        model=settings.LLM_MODEL,
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        temperature=0
    )
    # 使用结构化输出确保返回合法的过滤字典
    structured_llm = llm.with_structured_output(QueryFilter, method="function_calling")
    
    prompt = f"""你是一个数据库查询专家。请将用户的自然语言指令解析为针对 PostgreSQL JSONB 字段的过滤条件。
    
可用元数据字段：
- price (number): 价格
- brand (string): 品牌名
- city (string): 城市名
- doc_type (string): 文档类型 (product_specs, gadget_news, gourmet_review)
- category (string): 分类

过滤语法参考 (LangChain PGVector 格式)：
- {{"price": {{"$lt": 1000}}}} 表示价格小于 1000
- {{"brand": "Apple"}} 表示品牌为 Apple
- {{"city": {{"$in": ["北京", "上海"]}}}} 表示城市在北京或上海

用户指令："{query}"

请输出 JSON 格式的过滤字典和提取出的纯文本核心查询词。"""
    
    try:
        result = await structured_llm.ainvoke(prompt)
        print(f"🎯 [Self-Query] 解析过滤条件: {result.filter_dict} | 核心词: {result.refined_query}")
        return result
    except Exception as e:
        logger.warning(f"Self-Query 解析失败: {e}")
        return QueryFilter(filter_dict={}, refined_query=query)

async def retrieve_knowledge_hits(
    query: str,
    *,
    limit: int = 5,
    metadata_filter: Dict[str, Any] | None = None,
) -> dict[str, Any]:
    """统一的 RAG 召回层：支持 self-query、metadata filter 与混合检索。"""
    if not query:
        return {"hits": [], "mode": "empty", "parsed_filter": {}, "refined_query": ""}

    parsed = await _parse_self_query(query)
    merged_filter: Dict[str, Any] = {}
    if isinstance(parsed.filter_dict, dict):
        merged_filter.update(parsed.filter_dict)
    if isinstance(metadata_filter, dict):
        merged_filter.update({k: v for k, v in metadata_filter.items() if v is not None})

    logger.info("🔍 [RAG 检索] 正在通过结构化过滤 + 混合召回搜寻知识片段 (limit=%s)", limit)
    try:
        if merged_filter:
            async with generate_vector_store() as store:
                docs = await store.asimilarity_search(
                    parsed.refined_query,
                    k=limit,
                    filter=merged_filter,
                )
                hits = [
                    {
                        "page_content": d.page_content,
                        "metadata": dict(d.metadata or {}),
                        "score": None,
                    }
                    for d in docs
                ]
                mode = "vector_filtered"
        else:
            hits = await hybrid_search_rrf(parsed.refined_query, k=limit)
            mode = "hybrid_rrf"
        if not hits:
            logger.info("⚠️ [RAG 检索] 未找到匹配的私域知识。")
        return {
            "hits": hits,
            "mode": mode,
            "parsed_filter": merged_filter,
            "refined_query": parsed.refined_query,
        }
    except Exception as e:
        logger.error(f"RAG 检索失败: {e}")
        return {
            "hits": [],
            "mode": "error",
            "parsed_filter": merged_filter,
            "refined_query": parsed.refined_query,
            "error": str(e),
        }


async def retrieve_brand_knowledge(query: str, limit: int = 3) -> str:
    """
    【终极 RAG 检索引擎】：支持 Self-Query 过滤 + 混合召回 (Hybrid Search)。
    """
    result = await retrieve_knowledge_hits(query, limit=limit)
    hits = [item for item in (result.get("hits") or []) if isinstance(item, dict)]
    if not hits:
        return ""
    context = "\n---\n".join([str(r.get("page_content") or "") for r in hits if str(r.get("page_content") or "").strip()])
    logger.info("✅ [RAG 检索] 成功提取 %s 条强关联知识。", len(hits))
    return context
