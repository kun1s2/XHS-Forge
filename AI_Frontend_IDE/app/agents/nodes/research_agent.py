import asyncio
from typing import List, Dict, Optional, Any
from app.agents.state import UIProjectState
from app.agents.tools_registry import TOOL_POOL
from app.tools.serpapi_search import search_google_images
from langchain_core.messages import AIMessage, ToolMessage

# --- 🚀 事实哨兵 6.6：柔性取证版 ---

async def research_agent(state: UIProjectState) -> dict:
    """
    【事实哨兵 6.6】：根据意图信号按需取证，平衡效率与成本。
    """
    main_msgs = state.get("main_messages", [])
    if not main_msgs: return {}
    user_query = str(main_msgs[-1].content)

    # 1. 缓存嗅探
    from app.services.cache_service import cache_service
    hit_keywords = await cache_service.match_trends_in_text(user_query)
    if hit_keywords:
        cached = await cache_service.get_hot_knowledge(hit_keywords[0])
        if cached:
            print(f"🚀 [哨兵加速] 命中缓存: {hit_keywords[0]}")
            return {"retrieved_knowledge": cached}

    # 2. 信号提取
    intent_res = state.get("intent_result")
    asset_mode = getattr(intent_res, "asset_request", "NONE") if not isinstance(intent_res, dict) else intent_res.get("asset_request", "NONE")

    # 3. 并发取证决策
    search_tool = TOOL_POOL["network_search"]
    
    # 任务 A: 文本事实（对于 content_node 是刚需）
    search_task = search_tool.ainvoke({"query": f"{user_query} 深度资料"})
    
    # 任务 B: 图片打捞（柔性触发）
    # 只有当意图探测开启了 SEARCH 模式才启动
    should_search_images = (asset_mode == "SEARCH")
    image_task = search_google_images(query=f"{user_query} 真实素材图", num=5) if should_search_images else asyncio.sleep(0, result=[])

    print(f"📡 [搜证引擎] 正在作业... 文本: 物理强制 | 图片: {'已激活' if should_search_images else '已旁路'}")

    raw_web_content, real_image_urls = await asyncio.gather(search_task, image_task)

    # 构造 ToolMessage 容器
    text_tool_msg = ToolMessage(content=str(raw_web_content), tool_call_id="manual_search", name="network_search")
    img_tool_msg = ToolMessage(content="\n".join(real_image_urls) if real_image_urls else "", tool_call_id="manual_images", name="google_images")

    return {
        "messages": [text_tool_msg, img_tool_msg]
    }
