import json
from typing import List, Dict, Optional, Any
from app.agents.state import UIProjectState
from app.core.llm_factory import create_llm
from app.core.config import settings
from app.agents.tools_registry import TOOL_POOL
from langchain_core.messages import AIMessage
from app.services.cache_service import cache_service

# --- 🚀 决策大脑：只负责判断是否需要动用搜索工具 ---

async def get_trend_cache(query: str) -> Optional[Dict[str, Any]]:
    """
    语义缓存探测引擎：利用 Redis 高性能读取能力。
    """
    hit_keywords = await cache_service.match_trends_in_text(query)
    if hit_keywords:
        primary_keyword = hit_keywords[0]
        return await cache_service.get_hot_knowledge(primary_keyword)
    return None

def get_research_llm():
    return create_llm(
        model=settings.LLM_LOGIC_MODEL,
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        temperature=0
    ).bind_tools([TOOL_POOL["network_search"]])

async def research_agent(state: UIProjectState) -> dict:
    """
    【事实哨兵 4.0】：决策节点。
    """
    main_msgs = state.get("main_messages", [])
    if not main_msgs: return {"intent_route": "END"}
    user_query = str(main_msgs[-1].content)

    # 1. 优先嗅探热词缓存 (Redis)
    cached = await get_trend_cache(user_query)
    if cached:
        print("🚀 [哨兵加速] 命中热点缓存，直接跳过搜索。")
        cached["is_fact_ready"] = True
        return {"retrieved_knowledge": cached}

    # 2. 缓存未命中，强制触发工具决策
    llm = get_research_llm()
    print(f"🔎 [决策中] 正在评估话题「{user_query[:15]}」是否需要联网搜证...")
    
    # 构建高强度指令，强化竞品搜索
    system_msg = """你是一个严谨的搜证官。如果用户询问产品对比或参数，你必须调用 network_search。严禁根据记忆回答。
    【⚠️ 竞品搜索铁律】：如果用户的输入中包含两个或以上的竞争品牌（例如：华为和苹果，A7C2和R6），你在构建搜索查询词时，【必须】将这两个品牌同时包含在查询中（例如：‘华为 Mate 60 对比评测 iPhone 15’），绝不允许只搜索其中一个！"""
    
    # ✨ 核心：将指令写入总线，触发 LangGraph 的 Tool Calling 机制
    res = await llm.ainvoke([
        ("system", system_msg),
        ("human", f"请调研并对比以下内容：{user_query}")
    ])
    
    return {"messages": [res]}

def should_continue_research(state: UIProjectState) -> str:
    """
    路由逻辑：如果有 tool_calls，去执行工具；否则去蒸馏。
    """
    # 检查 messages 列表
    msgs = state.get("messages", [])
    if not msgs: return "distill_node"
    
    last_msg = msgs[-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "tools"
    return "distill_node"
