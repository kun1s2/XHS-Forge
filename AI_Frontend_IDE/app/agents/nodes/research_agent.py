import json
from typing import List, Dict, Optional, Any
from fastapi import HTTPException
from app.agents.state import UIProjectState
from app.core.llm_factory import create_llm
from app.core.config import settings
from app.core.schema import FocusedKnowledge
from app.services.mock_rag_service import retrieve_from_mock_db

# 🗡️ 选用逻辑模型进行强类型蒸馏，确保面试级稳定性
# 利用 .with_structured_output 实现真正的 Glassbox 结构化
structured_research_llm = create_llm(
    model=settings.LLM_LOGIC_MODEL,
    api_key=settings.LLM_API_KEY,
    base_url=settings.LLM_BASE_URL,
    temperature=0
).with_structured_output(FocusedKnowledge, method="function_calling")

async def research_agent(state: UIProjectState) -> dict:
    """
    【Vulcan-Prime 面试级节点】：阻塞式 RAG 热缓存命中与结构化蒸馏
    """
    print("▶️ [NODE START]: research_node (确定性结构化调研)")
    
    # 1. 提取用户指令
    active_panel = state.get("active_panel", "main")
    main_msgs = state.get("main_messages", [])
    if not main_msgs:
        return {"retrieved_knowledge": None}
        
    last_msg = main_msgs[-1]
    user_query = str(last_msg.content)
    
    # 2. 尝试从本地热缓存命中 (阻塞等待)
    print(f"🔍 [RAG 第一层] 正在匹配本地热缓存: {user_query}")
    raw_context = await retrieve_from_mock_db(user_query)
    
    if not raw_context:
        print("⚠️ [RAG 第一层] 未命中热缓存")
        # 为了演示稳定性，这里返回一个友好的空结构，防止下游产生幻觉
        return {
            "retrieved_knowledge": {
                "domain_category": "3C数码测评",
                "entity_name": "未知实体",
                "core_attributes": {},
                "summary": "未在热缓存中匹配到该实体。提示：尝试搜索‘小米17 Ultra’或‘海蓝之谜’。"
            }
        }

    # 3. 强制结构化蒸馏：将非结构化文本转化为强类型 JSON
    distill_prompt = f"""你是一个专业的数据结构化专家。
请将以下原始资料蒸馏为 FocusedKnowledge 格式。

【原始资料】:
{raw_context}

【输出指令】:
1. entity_name 必须是识别出的产品或地点全称。
2. core_attributes 必须提取出具体的参数键值对。
3. 严禁自由发挥，必须 100% 还原资料中的事实内容。
"""
    
    try:
        print("🧠 [RAG 蒸馏器] 正在执行 Pydantic 转换...")
        knowledge: FocusedKnowledge = await structured_research_llm.ainvoke(distill_prompt)
        
        if not knowledge:
            raise ValueError("大模型蒸馏失败 (返回值为 None)")
            
        print(f"✅ [NODE END]: research_node -> 成功结构化主体: {knowledge.entity_name}")
        
        # 4. 业务场景自动收束
        archetype_map = {
            "3C数码测评": "seeding",
            "线下探店打卡": "gourmet",
            "美妆个护种草": "seeding"
        }
        
        # 将 dump 后的字典写入状态机，供前端 inspect 接口读取
        return {
            "retrieved_knowledge": knowledge.model_dump(),
            "active_archetype": archetype_map.get(knowledge.domain_category, "general")
        }
        
    except Exception as e:
        print(f"❌ [RAG 蒸馏器] 严重错误: {e}")
        # 在面试级架构中，报错必须明确
        raise HTTPException(status_code=500, detail=f"RAG 结构化链路断裂: {str(e)}")

def should_continue_research(state: UIProjectState) -> str:
    """条件边：已废弃，现在走阻塞收束路径"""
    return "controversy_sniffer"
