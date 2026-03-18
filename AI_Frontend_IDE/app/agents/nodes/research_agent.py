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

# --- 🚀 事实哨兵 5.0：搜证提纯一体化 (源头治水版) ---

async def research_agent(state: UIProjectState) -> dict:
    """
    【事实哨兵 5.0】：不再利用 messages 传递废料。
    在节点内部完成 [搜索 -> 提纯 -> 销毁] 闭环。
    """
    main_msgs = state.get("main_messages", [])
    if not main_msgs: return {}
    user_query = str(main_msgs[-1].content)

    # 1. 语义缓存嗅探 (Redis)
    hit_keywords = await cache_service.match_trends_in_text(user_query)
    if hit_keywords:
        cached = await cache_service.get_hot_knowledge(hit_keywords[0])
        if cached:
            print(f"🚀 [哨兵加速] 命中缓存: {hit_keywords[0]}")
            cached["is_fact_ready"] = True
            return {"retrieved_knowledge": cached}

    # 2. 物理搜证启动
    print(f"🔎 [搜证中] 正在为「{user_query[:10]}...」抓取全网真实数据...")
    
    try:
        # ✨ 核心改进：直接调用工具，不经过 ToolNode 路由
        search_tool = TOOL_POOL["network_search"]
        # 我们手动构造工具输入，模拟大模型的 Tool Call 行为
        raw_web_content = await search_tool.ainvoke({"query": user_query})
        
        if not raw_web_content or len(str(raw_web_content)) < 50:
            print("⚠️ [搜证失败] 互联网未返回有效信息。")
            return {"retrieved_knowledge": {"is_fact_ready": False}}

        # 3. 现场提纯（就在本节点内，废料不入库）
        print(f"🧬 [现场提纯] 正在处理 {len(str(raw_web_content))} 字符的原始资料...")
        
        distill_llm = create_llm(
            model=settings.LLM_BRAIN_MODEL, 
            api_key=settings.LLM_API_KEY, 
            base_url=settings.LLM_BASE_URL,
            temperature=0
        )
        runnable = distill_llm.with_structured_output(FocusedKnowledge, method="function_calling")
        
        prompt = f"""你是一个极其严谨的数据提纯专家。
        请将以下【原始网页碎片】提炼为结构化事实。找不到的参数严禁脑补。
        【原始资料】:
        {raw_web_content}
        """
        
        knowledge: FocusedKnowledge = await runnable.ainvoke(prompt)
        
        if not knowledge or knowledge.entity_name in ["无", "未知"]:
            return {"retrieved_knowledge": {"is_fact_ready": False}}

        print(f"✅ [提纯完毕] 主体: {knowledge.entity_name} | 原始废料已随函数销毁")

        # 4. 异步持久化
        k_dict = knowledge.model_dump()
        k_dict["is_fact_ready"] = True
        asyncio.create_task(cache_service.set_hot_knowledge(knowledge.entity_name, k_dict))

        # ✨ 亮点：messages 总线只留下一条精简的“搜证完成”记录，不带任何废料
        status_msg = AIMessage(content=f"已完成对「{knowledge.entity_name}」的联网搜证，提取到 {len(k_dict.get('core_attributes', {}))} 项核心参数。")
        
        return {
            "retrieved_knowledge": k_dict,
            "messages": [status_msg]
        }

    except Exception as e:
        print(f"❌ [搜证链路断裂]: {e}")
        return {"retrieved_knowledge": {"is_fact_ready": False}}
