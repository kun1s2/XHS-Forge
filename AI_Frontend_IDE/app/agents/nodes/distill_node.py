import json
import asyncio
from typing import Dict, Any, List
from app.agents.state import UIProjectState
from app.core.llm_factory import create_llm
from app.core.config import settings
from app.core.schema import FocusedKnowledge
from app.services.cache_service import cache_service
from langchain_core.messages import ToolMessage, RemoveMessage

async def distill_node(state: UIProjectState) -> dict:
    """
    【事实提纯器】：根据搜索原始文本，进行分级提纯与存储。
    面试亮点：冷热数据分离治理 + 物理级总线卸载。
    """
    # 1. 寻找搜索工具的返回结果并收集需要销毁的消息 ID
    raw_search_results = ""
    messages_to_remove = []
    
    # 我们回溯总线消息，寻找本次 RAG 产生的 tool_call 和 tool_result
    all_msgs = state.get("messages", [])
    for msg in reversed(all_msgs):
        # 如果是工具返回的消息
        if isinstance(msg, ToolMessage):
            raw_search_results = str(msg.content)
            if msg.id: 
                messages_to_remove.append(RemoveMessage(id=msg.id))
        # 如果是发出工具调用的 AI 消息
        elif hasattr(msg, "tool_calls") and msg.tool_calls:
            if msg.id: 
                messages_to_remove.append(RemoveMessage(id=msg.id))
            # 找到成对的消息后，如果已经拿到了搜索结果，可以停止回溯
            if raw_search_results: 
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

【原始资料】:
{raw_search_results}
"""

    try:
        knowledge: FocusedKnowledge = await runnable.ainvoke(prompt)
        
        if not knowledge or knowledge.entity_name in ["无", "未知"]:
            return {"retrieved_knowledge": {"is_fact_ready": False}}

        print(f"✅ [提纯完毕] 识别到严谨主体: {knowledge.entity_name}")

        # 3. 分级异步入库逻辑
        async def persistence_worker():
            # 易变数据仅短期缓存
            await cache_service.set_hot_knowledge(knowledge.entity_name, knowledge.model_dump(), ttl=1800)

        asyncio.create_task(persistence_worker())

        k_dict = knowledge.model_dump()
        k_dict["is_fact_ready"] = True
        
        # ✨ 核心重构：不仅返回知识，还发出“物理卸载”指令
        # RemoveMessage 会被 add_messages reducer 识别并永久删除对应消息
        if messages_to_remove:
            print(f"🧹 [上下文工程] 已发出指令，物理销毁 {len(messages_to_remove)} 条 RAG 中间消息。")
        
        return {
            "retrieved_knowledge": k_dict,
            "messages": messages_to_remove # ✨ 关键：清理系统总线，防止状态爆炸
        }

    except Exception as e:
        print(f"❌ [蒸馏失败]: {e}")
        return {"retrieved_knowledge": {"is_fact_ready": False}}
