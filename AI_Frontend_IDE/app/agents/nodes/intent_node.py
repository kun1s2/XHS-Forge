import json
import re
import os
from pathlib import Path
from app.core.llm_factory import create_llm
from langchain_core.prompts import ChatPromptTemplate
from app.agents.state import UIProjectState
from app.core.config import settings
from app.core.schema import IntentOutput 
from app.services.scenario_manager import scenario_manager

# ✨ 性能优化：全局复用 LLM 实例
_llm_instance = None

def get_intent_llm():
    global _llm_instance
    if _llm_instance is None:
        os.environ["LANGSMITH_TRACING"] = "false"
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
    【意图路由大脑 3.0】：具备动态场景发现能力的智能网关。
    """
    llm = get_intent_llm()
    
    # 1. 动态获取当前系统安装的所有场景 ID（解耦核心）
    VALID_SCENARIOS = scenario_manager.list_all_scenarios()
    
    # 2. 状态提取
    data_dsl = state.get("data_dsl", {})
    selected_id = state.get("selected_element_id")
    active_archetype = state.get("active_archetype", "general")
    active_panel = state.get("active_panel", "main")
    
    messages = state.get(f"{active_panel}_messages", [])
    if not messages:
        return {"intent_route": "END"}
    user_query = messages[-1].content

    # 获取页面大纲 (ID + Type)
    outline = []
    if "root" in data_dsl:
        def walk(node):
            outline.append({"id": node["id"], "type": node["component_type"]})
            for child in node.get("children", []): walk(child)
        walk(data_dsl["root"])

    from datetime import datetime
    current_time = datetime.now().strftime("%Y-%m-%d %A")

    # 3. 加载提示词
    prompt_path = Path(__file__).parents[2] / "prompts" / "intent_system.xml"
    with open(prompt_path, "r", encoding="utf-8") as f:
        system_template = f.read()

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_template),
        ("human", "【当前时间】: {{ current_time }}\n【可用场景池】: {{ valid_scenarios }}\n【用户指令】: {{ query }}")
    ], template_format="jinja2")

    structured_llm = llm.with_structured_output(IntentOutput, method="function_calling")
    
    try:
        inputs = {
            "current_time": current_time,
            "valid_scenarios": ", ".join(VALID_SCENARIOS),
            "data_context": json.dumps(outline, ensure_ascii=False),
            "selected_element": selected_id if selected_id else "无", 
            "active_archetype": active_archetype, 
            "query": user_query
        }
        
        print(f"📡 [意图路由] 正在分析指令 4.0，支持场景: {VALID_SCENARIOS}")
        result: IntentOutput = await (prompt | structured_llm).ainvoke(inputs, config={"timeout": 45.0})
        
        # 4. 动态校验与补位
        detected_id = result.detected_element_id
        effective_id = selected_id or detected_id
        
        # 强制收束到已安装场景
        final_scenarios = [s for s in result.scenarios if s in VALID_SCENARIOS]
        if not final_scenarios: final_scenarios = ["general"]

        print(f"🎭 [六维雷达] 模式:{result.narrative_mode} | 烈度:{result.intensity_level:.1f} | 风格:{result.visual_vibe} | 靶向:{result.target_audience} | CTA:{result.call_to_action}")

        return {
            "intent_result": result,
            "intent_route": result.intent_route,
            "selected_element_id": effective_id,
            "scenarios": final_scenarios,
            "active_archetype": final_scenarios[0],
            "node_prompts": {"intent_agent": [{"role": "system", "content": f"6D Signal: Mode={result.narrative_mode}, Vibe={result.visual_vibe}, Audience={result.target_audience}, CTA={result.call_to_action}"}]}
        }
                
    except Exception as e:
        print(f"❌ Intent Agent 失败: {e}")
        return {"intent_route": "structure_node", "scenarios": ["general"]}
