import json
import asyncio
from typing import List, Dict, Optional, Any
from app.agents.state import UIProjectState
from app.core.llm_factory import create_llm
from app.core.config import settings
from app.core.schema import FocusedKnowledge
from app.agents.tools_registry import TOOL_POOL
from app.services.cache_service import cache_service
from langchain_core.messages import AIMessage, HumanMessage

# --- 🚀 事实哨兵 5.0：一体化 RAG (视觉资产增强版) ---

async def get_trend_cache(query: str) -> Optional[Dict[str, Any]]:
    """
    语义缓存探测引擎：利用 Redis 高性能读取能力。
    """
    hit_keywords = await cache_service.match_trends_in_text(query)
    if hit_keywords:
        primary_keyword = hit_keywords[0]
        return await cache_service.get_hot_knowledge(primary_keyword)
    return None

async def research_agent(state: UIProjectState) -> dict:
    """
    【事实哨兵 5.0】：一体化完成 [搜索 -> 提纯 -> 资产同步]。
    """
    main_msgs = state.get("main_messages", [])
    if not main_msgs: return {}
    user_query = str(main_msgs[-1].content)

    # 1. 缓存嗅探
    cached = await get_trend_cache(user_query)
    if cached:
        print("🚀 [哨兵加速] 命中热点缓存。")
        cached["is_fact_ready"] = True
        return {"retrieved_knowledge": cached}

    # 2. 物理搜证启动
    print(f"🔎 [搜证中] 正在为「{user_query[:10]}...」抓取全网真实事实与图片...")
    
    try:
        search_tool = TOOL_POOL["network_search"]
        # ✨ 强制要求搜索工具寻找“图片”和“评价”
        raw_web_content = await search_tool.ainvoke({"query": f"{user_query} 真实图片 评测参数"})
        
        if not raw_web_content or len(str(raw_web_content)) < 50:
            return {"retrieved_knowledge": {"is_fact_ready": False}}

        # 3. 现场提纯 (重点提取图片)
        distill_llm = create_llm(
            model=settings.LLM_BRAIN_MODEL, 
            api_key=settings.LLM_API_KEY, 
            base_url=settings.LLM_BASE_URL,
            temperature=0
        )
        runnable = distill_llm.with_structured_output(FocusedKnowledge, method="function_calling")
        
        prompt = f"""你是一个极其严谨的数据提纯专家。
        请将以下【原始网页碎片】提炼为结构化事实。
        
        【数据治理铁律】：
        1. 真实性：严禁脑补资料中不存在的参数！
        2. 视觉捕获：请务必提取资料中出现的【真实图片 URL】填入 image_urls。
        3. 对决主体：如果是对比，entity_name 必须包含双方。

【原始资料】:
{raw_web_content}
"""
        
        knowledge: FocusedKnowledge = await runnable.ainvoke(prompt)
        
        if not knowledge or knowledge.entity_name in ["无", "未知"]:
            return {"retrieved_knowledge": {"is_fact_ready": False}}

        print(f"✅ [提纯完毕] 主体: {knowledge.entity_name} | 提取到 {len(knowledge.image_urls)} 张图")

        # 4. 资产同步与异步持久化
        k_dict = knowledge.model_dump()
        k_dict["is_fact_ready"] = True
        
        # 将搜索到的图片转化为标准的 image_assets 格式
        new_assets = []
        for url in knowledge.image_urls:
            new_assets.append({
                "url": url,
                "desc": f"{knowledge.entity_name} 的实拍/宣传图"
            })

        asyncio.create_task(cache_service.set_hot_knowledge(knowledge.entity_name, k_dict))

        status_msg = AIMessage(content=f"已完成对「{knowledge.entity_name}」的联网搜证。")
        
        return {
            "retrieved_knowledge": k_dict,
            "image_assets": new_assets, # ✨ 同步更新资产库
            "messages": [status_msg]
        }

    except Exception as e:
        print(f"❌ [搜证失败]: {e}")
        return {"retrieved_knowledge": {"is_fact_ready": False}}
