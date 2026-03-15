import json
import re
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.agents.state import UIProjectState
from app.core.config import settings
from app.core.schema import SurgicalPatchOutput
from tenacity import retry, stop_after_attempt, wait_exponential

# ✨ 性能优化：全局复用 LLM 实例
_llm_instance = None

def get_patch_llm():
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = ChatOpenAI(
            model=settings.LLM_MODEL, 
            api_key=settings.LLM_API_KEY, 
            base_url=settings.LLM_BASE_URL, 
            temperature=0
        )
    return _llm_instance

def log_retry(retry_state):
    print(f"⚠️ [Patch Agent 重试] 尝试次数: {retry_state.attempt_number}, 错误原因: {retry_state.outcome.exception()}")

@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=5), before_sleep=log_retry)
async def invoke_patch_retry(chain, inputs):
    return await chain.ainvoke(inputs)

async def surgical_patch_agent(state: UIProjectState) -> dict:
    """
    【手术刀节点】：只针对选中的单个组件进行极速数据微调。
    """
    llm = get_patch_llm()
    # ✨ 性能优化：使用 json_mode
    structured_llm = llm.with_structured_output(SurgicalPatchOutput, method="json_mode")
    
    # 1. 锁定修改目标
    selected_id = state.get("selected_element_id")
    data_dsl = state.get("data_dsl", {})
    
    if not selected_id or selected_id not in data_dsl:
        print(f"⚠️ [Patch Node] 未找到选中的组件 {selected_id}，退回 structure_node")
        return {"intent_route": "structure_node"} # 降级处理

    target_component = data_dsl[selected_id]
    
    # 2. 提取用户指令
    main_msgs = state.get("main_messages", [])
    user_query = main_msgs[-1].content if main_msgs else ""
    if isinstance(user_query, list):
        user_query = str([item["text"] for item in user_query if item["type"] == "text"])

    # 3. 加载极简提示词
    prompt_path = Path(__file__).parents[2] / "prompts" / "patch_system.xml"
    with open(prompt_path, "r", encoding="utf-8") as f:
        system_template = f.read()

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_template),
        ("human", "修改指令: {{ query }}")
    ], template_format="jinja2")

    try:
        chain = prompt | structured_llm
        inputs = {
            "selected_element": selected_id,
            "target_component_json": json.dumps(target_component, ensure_ascii=False),
            "query": user_query
        }
        
        # ✨ 记录提示词快照用于前端调试
        rendered_messages = prompt.format_messages(**inputs)
        prompt_snapshot = [{"role": m.type, "content": m.content} for m in rendered_messages]

        result: SurgicalPatchOutput = await invoke_patch_retry(chain, inputs)
        
        print(f"💉 [手术刀修改成功] 目标: {selected_id} | 理由: {result.reason}")
        
        # 4. 构建局部补丁包
        # 仅更新被选中的那一个组件 ID 下的数据
        dsl_patch = {
            selected_id: {k: v for k, v in result.updated_component.model_dump().items() if v is not None}
        }
        
        return {
            "data_dsl": dsl_patch,
            "node_prompts": {"patch_node": prompt_snapshot}
        }
        
    except Exception as e:
        print(f"❌ Patch Agent 最终失败: {e}")
        return {}
