import json
import logging
from typing import Optional, Dict, List
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

async def retrieve_brand_knowledge(query: str, limit: int = 3) -> str:
    """
    【终极 RAG 检索引擎】：支持 Self-Query 过滤 + 混合召回 (Hybrid Search)。
    """
    if not query:
        return ""

    # 1. 预处理：解析语义过滤条件
    parsed = await _parse_self_query(query)
    
    print(f"🔍 [RAG 检索] 正在通过【混合召回】搜寻私域知识库 (Limit: {limit})...")
    
    try:
        # 2. 执行混合召回 (向量 + 全文检索)
        # 如果有解析出硬过滤条件，优先走 LangChain 向量检索（因为它处理 JSONB Filter 更成熟）
        if parsed.filter_dict:
            async with generate_vector_store() as store:
                docs = await store.asimilarity_search(
                    parsed.refined_query, 
                    k=limit,
                    filter=parsed.filter_dict
                )
                results = [{"page_content": d.page_content} for d in docs]
        else:
            # 如果没有硬过滤条件，走我们的原生混合召回以获得最佳相关性
            results = await hybrid_search_rrf(parsed.refined_query, k=limit)
            
        if not results:
            print("⚠️ [RAG 检索] 未找到匹配的私域知识。")
            return ""
        
        # 3. 拼接文档内容
        context = "\n---\n".join([r["page_content"] for r in results])
        print(f"✅ [RAG 检索] 成功提取 {len(results)} 条强关联知识。")
        return context
            
    except Exception as e:
        logger.error(f"RAG 检索失败: {e}")
        return ""
