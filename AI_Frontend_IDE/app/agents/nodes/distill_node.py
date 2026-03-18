import json
import asyncio
from typing import Dict, Any, List
from app.agents.state import UIProjectState
from app.core.llm_factory import create_llm
from app.core.config import settings
from app.core.schema import FocusedKnowledge
from app.services.cache_service import cache_service
from langchain_core.messages import ToolMessage

async def distill_node(state: UIProjectState) -> dict:
    """
    【事实提纯器】：根据搜索原始文本，进行分级提纯与存储。
    面试亮点：冷热数据分离治理，确保 RAG 严谨性。
    """
    # 1. 寻找搜索工具的返回结果
    raw_search_results = ""
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, ToolMessage):
            raw_search_results = str(msg.content)
            break
    
    if not raw_search_results:
        print("⚠️ [蒸馏器] 未找到原始搜索资料，判定为事实缺失。")
        return {"retrieved_knowledge": {"is_fact_ready": False}}

    # 2. 调用 LLM 进行结构化提纯
    llm = create_llm(
        model=settings.LLM_BRAIN_MODEL, 
        api_key=settings.LLM_API_KEY, 
        base_url=settings.LLM_BASE_URL,
        temperature=0
    )
    runnable = llm.with_structured_output(FocusedKnowledge, method="function_calling")
    
    prompt = f"""你是一个极其严谨的数据审计专家。
    请基于以下【原始网页文本】，提取出结构化事实。
    
    【数据治理宪法】：
    1. 真实性：严禁脑补资料中不存在的参数！找不到就填“未知”。
    2. 确定性：如果多个资料冲突，请在 summary 中注明“存在争议”。
    3. 区分度：请标记出哪些是“稳态事实”（如型号、发布时间），哪些是“瞬态事实”（如当前促销价、实时评价）。
    4. 对决主体：如果资料是关于两个产品的对比评测（如华为和苹果），你的 entity_name 必须包含双方，例如：'华为 Mate 60 vs iPhone 15'。

【原始资料】:
{raw_search_results}
"""

    try:
        knowledge: FocusedKnowledge = await runnable.ainvoke(prompt)
        
        if not knowledge or knowledge.entity_name in ["无", "未知"]:
            return {"retrieved_knowledge": {"is_fact_ready": False}}

        print(f"✅ [提纯完毕] 识别到严谨主体: {knowledge.entity_name}")

        # 3. ✨ 面试亮点：分级异步入库逻辑
        # 稳态事实 -> 存入持久层 (Vector DB 模拟)
        # 瞬态事实 -> 存入 Redis (短 TTL)
        async def persistence_worker():
            # 模拟持久化操作
            print(f"💾 [异步持久化] 正在将「{knowledge.entity_name}」的稳态事实写入知识库...")
            # cache_service.set_strict_knowledge(knowledge.entity_name, ...) 
            
            # 易变数据仅短期缓存
            await cache_service.set_hot_knowledge(knowledge.entity_name, knowledge.model_dump(), ttl=1800)

        asyncio.create_task(persistence_worker())

        k_dict = knowledge.model_dump()
        k_dict["is_fact_ready"] = True
        return {"retrieved_knowledge": k_dict}

    except Exception as e:
        print(f"❌ [蒸馏失败]: {e}")
        return {"retrieved_knowledge": {"is_fact_ready": False}}
