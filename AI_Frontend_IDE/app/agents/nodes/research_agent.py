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
def get_research_llm():
    return create_llm(
        model=settings.LLM_LOGIC_MODEL,
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        temperature=0
    )

async def research_agent(state: UIProjectState) -> dict:
    """
    【Vulcan-Prime 4.0】：执行“按需资产”策略与阻塞式蒸馏
    """
    print("▶️ [NODE START]: research_node (资产权限受控调研)")
    
    # 1. 提取 4.0 资产权限信号
    intent_res = state.get("intent_result")
    asset_mode = getattr(intent_res, "asset_request", "NONE") if intent_res else "NONE"
    scenarios = state.get("scenarios", ["general"])
    scenario_id = scenarios[0]
    
    # 2. 动态挂载工具箱
    scenario_config = scenario_manager.get_config(scenario_id)
    allowed_list = scenario_config.get("allowed_tools", [])
    
    # 物理隔离
    available_tools = [TOOL_POOL[name] for name in allowed_list if name in TOOL_POOL]
    
    # 只有在申请了搜索或生图时，才在模型中绑定图像工具
    final_tools = [TOOL_POOL["network_search"]] # 默认必给网络搜索
    if asset_mode == "SEARCH" and "google_images" in allowed_list:
        final_tools.append(TOOL_POOL["google_images"])
    if asset_mode == "GENERATE" and "image_generation" in allowed_list:
        final_tools.append(TOOL_POOL["image_generation"])
        
    # ✨ 核心修复：先绑定工具，再应用结构化输出
    base_llm = get_research_llm()
    llm_with_tools = base_llm.bind_tools(final_tools)
    runnable = llm_with_tools.with_structured_output(FocusedKnowledge, method="function_calling")
    
    # 3. 提取用户指令与热缓存
    active_panel = state.get("active_panel", "main")
    main_msgs = state.get("main_messages", [])
    if not main_msgs: return {"retrieved_knowledge": None}
    user_query = str(main_msgs[-1].content)
    
    raw_context = await retrieve_from_mock_db(user_query) or "未匹配到本地事实。"

    # 4. 强制结构化蒸馏
    distill_prompt = f"""你是一个专业的数据结构化专家。
当前场景：{scenario_id} | 资产模式：{asset_mode}

【原始资料】:
{raw_context}

【4.0 资产分发铁律】:
1. 如果 asset_mode == "SEARCH": 你必须调用 google_images 搜集 3 张图并存入 image_urls。
2. 如果 asset_mode == "GENERATE": 你必须调用 image_generation 画 1 张图并存入 image_urls。
3. 如果 asset_mode == "NONE": 绝对禁止找图！image_urls 字段必须保持为空 []。

【其他指令】:
- entity_name 必须是识别出的产品或地点全称。
- 严禁捏造，必须 100% 还原事实。
"""
    
    try:
        print(f"🧠 [RAG 蒸馏器] 执行场景 [{scenario_id}] 转换，资产权限: {asset_mode}")
        knowledge: FocusedKnowledge = await runnable.ainvoke(distill_prompt)
        
        if not knowledge: raise ValueError("大模型蒸馏失败 (None)")
            
        print(f"✅ [NODE END]: research_node -> 识别主体: {knowledge.entity_name} | 图片数: {len(knowledge.image_urls)}")
        
        return {
            "retrieved_knowledge": knowledge.model_dump(),
            "active_archetype": scenario_id
        }
        
    except Exception as e:
        print(f"❌ [RAG 蒸馏器] 严重错误: {e}")
        raise HTTPException(status_code=500, detail=f"4.0 资产路由故障: {str(e)}")

def should_continue_research(state: UIProjectState) -> str:
    return "controversy_sniffer"
