import asyncio
from typing import List, Dict, Optional, Any
from app.agents.state import UIProjectState
from app.agents.tools_registry import TOOL_POOL
from app.agents.utils.entity_utils import normalize_entity_name
from app.tools.serpapi_search import search_google_images
from langchain_core.messages import AIMessage, ToolMessage

# --- 🚀 事实哨兵 6.6：柔性取证版 ---

async def research_agent(state: UIProjectState) -> dict:
    """
    【事实哨兵 6.6】：根据意图信号按需取证，平衡效率与成本。
    """
    def _extract_user_text(message_content: Any) -> str:
        if isinstance(message_content, list):
            return "".join(
                str(part.get("text"))
                for part in message_content
                if isinstance(part, dict) and part.get("type") == "text" and part.get("text")
            ).strip()
        return str(message_content or "").strip()

    main_msgs = state.get("main_messages", [])
    if not main_msgs: return {}
    user_query = _extract_user_text(main_msgs[-1].content)
    entity_name = normalize_entity_name(user_query)

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
    # 在这里可以拆分为两个关键词进行并发，模拟 plan-and-solve 降延迟
    # 如果失败，底层 tool 自己应该有容错，如果还想强制限制：
    search_task_1 = search_tool.ainvoke({"query": f"{user_query} 核心参数 价格 官方"})
    search_task_2 = search_tool.ainvoke({"query": f"{user_query} 用户评价 真实体验"})
    
    # 任务 B: 图片打捞（柔性触发）
    # 只有当意图探测开启了 SEARCH 模式才启动
    should_search_images = (asset_mode == "SEARCH")
    image_task = search_google_images(query=f"{user_query} 真实素材图", num=5) if should_search_images else asyncio.sleep(0, result=[])

    print(f"📡 [搜证引擎] 正在作业... 文本: 并发多路强取 | 图片: {'已激活' if should_search_images else '已旁路'}")

    try:
        results = await asyncio.wait_for(asyncio.gather(search_task_1, search_task_2, image_task), timeout=25.0)
        raw_web_content_1, raw_web_content_2, real_image_urls = results
        raw_web_content = f"""【官方资料】:
{raw_web_content_1}
【用户评价】:
{raw_web_content_2}"""
    except Exception as e:
        print(f"⚠️ [搜证引擎] 物理强取超时或失败: {e}，返回兜底空数据。")
        raw_web_content = "无网络数据"
        real_image_urls = []

    # 构造虚假的 AIMessage 包含 tool_calls
    fake_ai_msg = AIMessage(
        content="",
        tool_calls=[
            {"name": "network_search", "args": {"query": f"{user_query} 深度资料"}, "id": "manual_search"},
            {"name": "google_images", "args": {"query": f"{user_query} 真实素材图"}, "id": "manual_images"}
        ]
    )

    # 构造 ToolMessage 容器 (已废弃，直接注入知识库)
    # text_tool_msg = ToolMessage(...)

    print(f"✅ [搜证完毕] 已获取真实文本与 {len(real_image_urls) if real_image_urls else 0} 条图片直链。")

    # 构造 image_assets 结构
    final_assets = [{"url": u, "desc": f"{user_query} 实拍图"} for u in real_image_urls]

    return {
        # 直接将战术情报返回给全局状态，而不是去污染聊天记录！
        "retrieved_knowledge": {
            "entity_name": entity_name or user_query,
            "is_fact_ready": True,
            "battle_report": None, # 暂时置空，交由 downstream 处理
            "text_facts": str(raw_web_content) # 保留原始文本供提纯
        },
        "image_assets": final_assets,
        # 仅返回一条简短的系统通知
        "messages": [AIMessage(content=f"已完成对「{entity_name or user_query}」的物理搜证。")]
    }
