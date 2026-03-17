import json
from typing import List, Dict, Optional, Any
from fastapi import HTTPException
from app.agents.state import UIProjectState
from app.core.llm_factory import create_llm
from app.core.config import settings
from app.core.schema import FocusedKnowledge
from app.services.mock_rag_service import retrieve_from_mock_db
from app.services.scenario_manager import scenario_manager
from app.agents.tools_registry import TOOL_POOL

async def research_agent(state: UIProjectState) -> dict:
    """
    【Vulcan-Prime 3.0】：阻塞式 RAG 与工具池权限隔离 (修复 bind_tools 顺序错误)
    """
    print("▶️ [NODE START]: research_node (场景自治调研)")
    
    # 1. 场景探测
    scenarios = state.get("scenarios", [])
    scenario_id = scenarios[0] if scenarios else "general"
    
    # 2. 动态构建 LLM 链 (✨ 核心修复：先绑定工具，再结构化输出)
    base_llm = create_llm(
        model=settings.LLM_LOGIC_MODEL,
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        temperature=0
    )
    
    scenario_config = scenario_manager.get_config(scenario_id)
    allowed_names = scenario_config.get("allowed_tools", [])
    
    # 物理过滤
    available_tools = [TOOL_POOL[name] for name in allowed_names if name in TOOL_POOL]
    if not available_tools:
        available_tools = [TOOL_POOL["network_search"]]
    
    # 🌟 正确的时序：BaseLLM -> Bind Tools -> Structured Output
    # 注意：在大模型同时使用 tools 和 structured_output 时，某些中转商可能会困惑。
    # 这里的 FocusedKnowledge 是最终必须输出的契约。
    llm_with_tools = base_llm.bind_tools(available_tools)
    runnable = llm_with_tools.with_structured_output(FocusedKnowledge, method="function_calling")
    
    # 3. 提取用户指令与热缓存
    active_panel = state.get("active_panel", "main")
    main_msgs = state.get("main_messages", [])
    if not main_msgs:
        return {"retrieved_knowledge": None}
        
    last_msg = main_msgs[-1]
    user_query = str(last_msg.content)
    
    print(f"🔍 [RAG 层] 场景 [{scenario_id}] 正在匹配本地热缓存: {user_query}")
    raw_context = await retrieve_from_mock_db(user_query)
    
    if not raw_context:
        # ✨ 哨兵修复：兼容函数对象和工具对象的名称读取
        tool_names = [getattr(t, 'name', getattr(t, '__name__', str(t))) for t in available_tools]
        print(f"⚠️ [RAG 层] 未命中热缓存，当前场景可用工具: {tool_names}")
        raw_context = "未匹配到热缓存事实数据。请尝试调用工具获取。"

    # 4. 执行蒸馏
    distill_prompt = f"""你是一个专业的数据结构化专家。
当前场景：{scenario_id}
请利用可用工具（如果资料不足）或原始资料，将内容蒸馏为 FocusedKnowledge 格式。

【原始资料】:
{raw_context}

【指令】:
1. entity_name 必须是识别出的产品或地点全称。
2. 严禁捏造，必须 100% 还原事实。
"""
    
    try:
        print(f"🧠 [RAG 蒸馏器] 正在执行场景转换...")
        knowledge: FocusedKnowledge = await runnable.ainvoke(distill_prompt)
        
        if not knowledge:
            raise ValueError("大模型蒸馏失败 (None)")
            
        print(f"✅ [NODE END]: research_node -> 结构化主体: {knowledge.entity_name}")
        
        return {
            "retrieved_knowledge": knowledge.model_dump(),
            "active_archetype": scenario_id
        }
        
    except Exception as e:
        print(f"❌ [RAG 蒸馏器] 严重错误: {e}")
        raise HTTPException(status_code=500, detail=f"场景自治链路故障: {str(e)}")

def should_continue_research(state: UIProjectState) -> str:
    return "controversy_sniffer"
