import json
import re
import os
from pathlib import Path
from app.core.llm_factory import create_llm
from langchain_core.prompts import ChatPromptTemplate
from app.agents.state import UIProjectState
from app.core.config import settings
from app.core.schema import ArchetypeEnum, IntentOutput

# ✨ 性能优化：全局复用“物理直连”LLM 实例
_llm_instance = None

def get_intent_llm():
    global _llm_instance
    if _llm_instance is None:
        # ✨ 1. 强制禁用可能引发阻塞的 LangSmith 追踪
        os.environ["LANGSMITH_TRACING"] = "false"
        
        # 🗡️ 哨兵三轨制：逻辑路由切换为专门的 LOGIC 模型
        _llm_instance = create_llm(
            model=settings.LLM_LOGIC_MODEL, 
            api_key=settings.LLM_API_KEY, 
            base_url=settings.LLM_BASE_URL, 
            temperature=0,
            max_retries=1
        )
    return _llm_instance

async def intent_agent(state: UIProjectState) -> dict:
    """
    【意图大脑 4.0：混合路由架构】
    结合“确定性拦截 (Deterministic Override)”与“LLM 模糊推理”，
    实现极速、零误判的流量分发。
    """
    active_panel = state.get("active_panel", "main")
    data_dsl = state.get("data_dsl", {})
    selected_id = state.get("selected_element_id")

    # ========================================================
    # 🛡️ 核心优化 1：确定性快速通道 (Fast-path Override)
    # 如果用户选中了组件，且面板不是主面板，直接拦截流量，不经过大模型！
    # 极大节省 Token，且将路由错误率降至 0%
    # ========================================================
    if selected_id and selected_id in data_dsl and active_panel != "main":
        print(f"⚡ [极速路由] 检测到明确的局部修改意图，目标组件: {selected_id}，直接放行至 patch_node")
        return {
            "intent_route": "patch_node",
            "active_archetype": state.get("active_archetype", "general")
        }

    messages = state.get(f"{active_panel}_messages", [])
    
    if not messages:
        return {"intent_route": "content_node", "active_archetype": "general"}
        
    last_msg = messages[-1]
    user_query = " ".join([item["text"] for item in last_msg.content if item.get("type") == "text"]) if isinstance(last_msg.content, list) else str(last_msg.content)

    print(f"\n\033[94m👤 [用户输入]: {user_query}\033[0m")

    # ✨ 真正的懒加载：仅当未命中 Fast-path 且需要 LLM 推理时才初始化，达到 O(1) 极速通道
    llm = get_intent_llm()

    # 全局意图分支：进入 LLM 路由...
    prompt_path = Path(__file__).parents[2] / "prompts" / "intent_system.xml"
    with open(prompt_path, "r", encoding="utf-8") as f:
        system_template = f.read()

    active_archetype = state.get("active_archetype", "general")
    
    # ========================================================
    # 🛡️ 核心优化 2：Token 瘦身 (Outline Extraction)
    # 只提取大纲，不传全量数据
    # ========================================================
    outline = {k: v.get("type") or v.get("component_type") for k, v in data_dsl.items() if isinstance(v, dict)} if data_dsl else "空"

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_template),
        ("human", "【当前场景背景】: {{ active_archetype }}\n用户的最新指令：\n<user_input>\n{{ query }}\n</user_input>\n(请通过调用工具输出 JSON 格式结果)")
    ], template_format="jinja2")
    
    from datetime import datetime
    current_time = datetime.now().strftime("%Y-%m-%d %A")
    
    try:
        inputs = {
            "current_time": current_time,  # ✨ 哨兵注入：系统当前时间
            "data_context": json.dumps(outline, ensure_ascii=False),  # ✨ 只传大纲
            "selected_element": selected_id if selected_id else "无", 
            "active_archetype": active_archetype, 
            "query": user_query
        }
        
        # 🌟 既然长官确认支持，回归 function_calling 模式
        structured_llm = llm.with_structured_output(IntentOutput, method="function_calling")
        
        print(f"📡 正在发起【结构化意图】识别...")
        # ✨ 给复杂的意图识别多留 15 秒宽限期
        runnable = prompt | structured_llm
        result: IntentOutput = await runnable.ainvoke(inputs, config={"timeout": 45.0})
        
        rendered_messages = prompt.format_messages(**inputs)
        prompt_data = [{"role": m.type, "content": m.content} for m in rendered_messages]
        archetype_str = result.detected_archetype.value if hasattr(result.detected_archetype, 'value') else str(result.detected_archetype)
        
        # 🌟 捕获潜在修改目标
        detected_id = result.detected_element_id
        final_route = result.intent_route
        
        # 如果 LLM 识别出了具体目标，且当前 state 没选，则自动“补位”选中它，辅助 patch_node
        effective_id = selected_id or detected_id
        
        return {
            "intent_result": result,
            "intent_route": final_route,
            "selected_element_id": effective_id, # ✨ 注入识别出的 ID
            "scenarios": result.scenarios,
            "active_archetype": archetype_str,
            "node_prompts": {"intent_agent": prompt_data}
        }
        
    except Exception as e:
        print(f"❌ Intent Agent 最终失败: {e}")
        # ========================================================
        # 🛡️ 核心优化 3：返回合法的 Pydantic 对象防止雪崩
        # ========================================================
        fallback_route = "content_node" if not data_dsl else "structure_node"
        fallback_result = IntentOutput(
            thought_process="系统异常，进入安全降级模式。",
            reason=f"系统报错兜底: {str(e)}",
            intent_route=fallback_route,
            scenarios=["general"],
            detected_archetype=ArchetypeEnum.GENERAL
        )
        return {
            "intent_result": fallback_result,
            "intent_route": fallback_route,
            "scenarios": ["general"],
            "active_archetype": "general",
            "node_prompts": {"intent_agent": []}
        }
