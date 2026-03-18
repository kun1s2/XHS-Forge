import json
import asyncio
import re
from typing import List, Dict, Optional, Any
from app.agents.state import UIProjectState
from app.core.llm_factory import create_llm
from app.core.config import settings
from app.core.schema import FocusedKnowledge
from app.agents.tools_registry import TOOL_POOL
from app.services.cache_service import cache_service
from langchain_core.messages import AIMessage, HumanMessage

# --- 🚀 事实哨兵 5.5：深度锚定与视觉穿透版 ---

async def research_agent(state: UIProjectState) -> dict:
    """
    【事实哨兵 5.5】：强化实体锚定，过滤网络噪音，强制提取高清图片。
    """
    main_msgs = state.get("main_messages", [])
    if not main_msgs: return {}
    user_query = str(main_msgs[-1].content)

    # 1. 缓存嗅探
    hit_keywords = await cache_service.match_trends_in_text(user_query)
    if hit_keywords:
        cached = await cache_service.get_hot_knowledge(hit_keywords[0])
        if cached:
            print("🚀 [哨兵加速] 命中热点缓存。")
            cached["is_fact_ready"] = True
            return {"retrieved_knowledge": cached}

    # 2. 物理搜证启动（强化 Query）
    # 增加 -未来 -预测 等词，防止搜到假新闻
    clean_query = f"{user_query} 参数 评价 官网实拍图 -未来 -预测 -假想图"
    print(f"🔎 [深度搜证] 正在抓取「{user_query[:10]}」的真实事实与直链图片...")
    
    try:
        search_tool = TOOL_POOL["network_search"]
        raw_web_content = await search_tool.ainvoke({"query": clean_query})
        
        if not raw_web_content or len(str(raw_web_content)) < 50:
            return {"retrieved_knowledge": {"is_fact_ready": False}}

        # 3. 现场提纯 (强化图片正则提取)
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
        1. 过滤噪音：严禁提及未来产品、传闻或爆料（如搜到 Mate 80 但用户问的是 Mate 60，请忽略 Mate 80）。
        2. 视觉捕获：请从文本中疯狂搜寻图片直链（必须以 http 开头，以 .jpg, .png, .webp 结尾）。提取 3-5 张填入 image_urls。
        3. 真实性：100% 依据资料，找不到不编。

【原始资料】:
{raw_web_content}
"""
        
        knowledge: FocusedKnowledge = await runnable.ainvoke(prompt)
        
        # 兜底：如果模型没提取到图，我们用多重正则进行物理打捞
        if not knowledge.image_urls:
            # 匹配常见的图片后缀，排除图标类小图
            raw_str = str(raw_web_content)
            # 排除 1x1, icon, logo 等关键词
            pattern = r'https?://[^\s<>"]+?\.(?:jpg|jpeg|png|webp)'
            potential_urls = re.findall(pattern, raw_str)
            
            cleaned_urls = []
            for u in potential_urls:
                u_lower = u.lower()
                if any(x in u_lower for x in ["icon", "logo", "avatar", "1x1", "pixel"]): continue
                if u not in cleaned_urls: cleaned_urls.append(u)
            
            knowledge.image_urls = cleaned_urls[:5]

        if not knowledge or knowledge.entity_name in ["无", "未知"]:
            return {"retrieved_knowledge": {"is_fact_ready": False}}

        print(f"✅ [提纯完毕] 主体: {knowledge.entity_name} | 捕获图片: {len(knowledge.image_urls)}")

        # 4. 资产同步
        k_dict = knowledge.model_dump()
        k_dict["is_fact_ready"] = True
        
        new_assets = []
        for url in knowledge.image_urls:
            new_assets.append({"url": url, "desc": f"{knowledge.entity_name} 真实素材"})

        asyncio.create_task(cache_service.set_hot_knowledge(knowledge.entity_name, k_dict))

        return {
            "retrieved_knowledge": k_dict,
            "image_assets": new_assets, 
            "messages": [AIMessage(content=f"已完成对「{knowledge.entity_name}」的搜证。")]
        }

    except Exception as e:
        print(f"❌ [搜证异常]: {e}")
        return {"retrieved_knowledge": {"is_fact_ready": False}}
