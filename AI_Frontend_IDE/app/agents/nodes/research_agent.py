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

# 🗡️ 选用逻辑模型进行强类型蒸馏，确保面试级稳定性
structured_research_llm = create_llm(
    model=settings.LLM_LOGIC_MODEL,
    api_key=settings.LLM_API_KEY,
    base_url=settings.LLM_BASE_URL,
    temperature=0
).with_structured_output(FocusedKnowledge, method="function_calling")

async def research_agent(state: UIProjectState) -> dict:
    """
    【Vulcan-Prime 3.0】：阻塞式 RAG 与专家工具箱按需挂载
    """
    print("▶️ [NODE START]: research_node (场景自治调研)")
    
    # 1. 场景探测与工具动态裁剪
    scenarios = state.get("scenarios", [])
    scenario_id = scenarios[0] if scenarios else "general"
    
    scenario_config = scenario_manager.get_config(scenario_id)
    allowed_list = scenario_config.get("allowed_tools", [])
    
    # 物理过滤：仅激活当前场景被授权的工具
    available_tools = [TOOL_POOL[name] for name in allowed_list if name in TOOL_POOL]
    # 安全降级：默认提供基础搜索
    if not available_tools:
        available_tools = [TOOL_POOL["network_search"]]
    
    # 动态绑定专家工具集
    llm_with_tools = structured_research_llm.bind_tools(available_tools)
    
    # 2. 提取用户指令与热缓存
    active_panel = state.get("active_panel", "main")
    main_msgs = state.get("main_messages", [])
    if not main_msgs:
        return {"retrieved_knowledge": None}
        
    last_msg = main_msgs[-1]
    user_query = str(last_msg.content)
    
    print(f"🔍 [RAG 层] 场景 [{scenario_id}] 正在匹配本地热缓存: {user_query}")
    raw_context = await retrieve_from_mock_db(user_query)
    
    if not raw_context:
        print(f"⚠️ [RAG 层] 未命中热缓存，已准备专家工具: {[t.name for t in available_tools]}")
        raw_context = "未匹配到热缓存事实数据。"

    # 3. 强制结构化蒸馏
    distill_prompt = f"""你是一个专业的数据结构化专家。
当前场景：{scenario_id}
请利用可用工具或提供的原始资料，将内容蒸馏为 FocusedKnowledge 格式。

【原始资料】:
{raw_context}

【指令】:
1. entity_name 必须是识别出的产品或地点全称。
2. 严禁捏造，必须 100% 还原事实。
"""
    
    try:
        print(f"🧠 [RAG 蒸馏器] 执行场景 [{scenario_id}] 级转换...")
        knowledge: FocusedKnowledge = await llm_with_tools.ainvoke(distill_prompt)
        
        if not knowledge:
            raise ValueError("大模型蒸馏失败 (None)")
            
        print(f"✅ [NODE END]: research_node -> 成功识别主体: {knowledge.entity_name}")
        
        return {
            "retrieved_knowledge": knowledge.model_dump(),
            "active_archetype": scenario_id
        }
        
    except Exception as e:
        print(f"❌ [RAG 蒸馏器] 严重错误: {e}")
        raise HTTPException(status_code=500, detail=f"场景自治链路故障: {str(e)}")

def should_continue_research(state: UIProjectState) -> str:
    """条件边：已废弃，现在走阻塞收束路径"""
    return "controversy_sniffer"
