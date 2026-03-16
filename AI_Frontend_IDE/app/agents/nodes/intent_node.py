import json
import re
import os
import httpx
from pathlib import Path
from app.core.llm_factory import create_llm
from langchain_core.prompts import ChatPromptTemplate
from app.agents.state import UIProjectState
from app.core.config import settings
from app.core.schema import ArchetypeEnum, IntentOutput
from app.agents.memory_utils import get_trimmed_messages # ✨ 引入记忆截断器

# ✨ 性能优化：全局复用“物理直连”LLM 实例
_llm_instance = None

def get_intent_llm():
    global _llm_instance
    if _llm_instance is None:
        # ✨ 1. 强制禁用可能引发阻塞的 LangSmith 追踪
        os.environ["LANGSMITH_TRACING"] = "false"
        
        # ✨ 代码净化：移除之前的硬编码物理直连，交还给系统的标准 httpx
        _llm_instance = create_llm(
            model=settings.LLM_MODEL, 
            api_key=settings.LLM_API_KEY, 
            base_url=settings.LLM_BASE_URL, 
            temperature=0,
            max_retries=1
        )
    return _llm_instance

async def intent_agent(state: UIProjectState) -> dict:
    """
    【意图大脑 4.0】：回归极致简洁，确保 Tool Calling 协议不被截断逻辑干扰。
    """
    llm = get_intent_llm()
    
    # 1. 直接取最后一轮对话，不进行复杂的 trim，防止协议污染
    active_panel = state.get("active_panel", "main")
    messages = state.get(f"{active_panel}_messages", [])
    
    if not messages:
        return {"intent_route": "content_node", "active_archetype": "general"}
        
    last_msg = messages[-1]
    # 提取纯文本内容
    if isinstance(last_msg.content, list):
        user_query = " ".join([item["text"] for item in last_msg.content if item.get("type") == "text"])
    else:
        user_query = str(last_msg.content)

    print(f"\n\033[94m👤 [用户输入]: {user_query}\033[0m")

    # 2. 构造提示词（Jinja2）
    prompt_path = Path(__file__).parents[2] / "prompts" / "intent_system.xml"
    with open(prompt_path, "r", encoding="utf-8") as f:
        system_template = f.read()

    active_archetype = state.get("active_archetype", "general")
    data_dsl = state.get("data_dsl", {})
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_template),
        ("human", "【当前场景背景】: {{ active_archetype }}\n用户的最新指令：\n<user_input>\n{{ query }}\n</user_input>\n(请通过调用工具输出 JSON 格式结果)")
    ], template_format="jinja2")
    
    try:
        inputs = {
            "data_context": json.dumps(data_dsl, ensure_ascii=False) if data_dsl else "空",
            "selected_element": state.get("selected_element_id", "无"),
            "active_archetype": active_archetype, 
            "query": user_query
        }
        
        # 3. 极速调用：强制 function_calling
        structured_llm = llm.with_structured_output(IntentOutput, method="function_calling")
        
        print(f"📡 正在发起【结构化意图】识别...")
        result = await (prompt | structured_llm).ainvoke(inputs)
        
        # 4. 结果处理
        rendered_messages = prompt.format_messages(**inputs)
        prompt_data = [{"role": m.type, "content": m.content} for m in rendered_messages]
        archetype_str = result.detected_archetype.value if hasattr(result.detected_archetype, 'value') else str(result.detected_archetype)
        
        return {
            "intent_result": result,
            "intent_route": result.intent_route,
            "scenarios": result.scenarios,
            "active_archetype": archetype_str,
            "node_prompts": {"intent_agent": prompt_data}
        }
        
    except Exception as e:
        print(f"❌ Intent Agent 最终失败: {e}")
        # ✨ 修复：兜底数据必须符合 IntentOutput Pydantic 模型，否则会报 ValidationError
        return {
            "intent_result": {
                "thought_process": "系统异常，进入安全降级模式。",
                "reason": "系统报错兜底",
                "intent_route": "content_node" if not data_dsl else "structure_node",
                "scenarios": ["general"],
                "detected_archetype": "general"
            },
            "intent_route": "content_node" if not data_dsl else "structure_node",
            "scenarios": ["general"],
            "active_archetype": "general",
            "node_prompts": {"intent_agent": []}
        }
