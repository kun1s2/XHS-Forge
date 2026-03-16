import json
from pathlib import Path
from app.core.llm_factory import create_llm
from langchain_core.prompts import ChatPromptTemplate
from app.agents.state import UIProjectState
from app.core.config import settings
from app.core.schema import OutlineOutput # 需在 schema.py 中定义
from tenacity import retry, stop_after_attempt, wait_exponential

# ✨ 性能优化：全局复用 LLM 实例
_llm_instance = None

def get_outline_llm():
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = create_llm(
            model=settings.LLM_MODEL, 
            api_key=settings.LLM_API_KEY, 
            base_url=settings.LLM_BASE_URL, 
            temperature=0.3
        )
    return _llm_instance

def log_retry(retry_state):
    print(f"⚠️ [Outline Agent 重试] 尝试次数: {retry_state.attempt_number}, 错误原因: {retry_state.outcome.exception()}")

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), before_sleep=log_retry)
async def invoke_with_retry(chain, inputs):
    return await chain.ainvoke(inputs)

async def outline_agent(state: UIProjectState) -> dict:
    """
    【裂变大纲节点】：只负责输出组件的 ID 列表和类型（Map 阶段的准备）。
    """
    llm = get_outline_llm()
    # ✨ 针对 OpenAI 模型使用 function_calling 更稳健
    structured_llm = llm.with_structured_output(OutlineOutput, method="function_calling")
    
    # 提取当前状态
    current_data_dsl = state.get("data_dsl", {})
    selected_element = state.get("selected_element_id", "无 (全局修改)")
    active_archetype = state.get("active_archetype", "general")
    
    main_msgs = state.get("main_messages", [])
    user_query = main_msgs[-1].content if main_msgs else "请根据要求规划页面大纲"
    if isinstance(user_query, list):
        user_query = str([item["text"] for item in user_query if item["type"] == "text"])
    
    content_msgs = state.get("content_messages", [])
    content_context = content_msgs[-1].content if content_msgs else "无特定的前置文案要求。"

    assets = state.get("image_assets", [])
    assets_text = json.dumps(assets, ensure_ascii=False) if assets else "无"
    is_update = bool(current_data_dsl and current_data_dsl.get("page_order"))

    # 复用排版的提示词，或者可以建立专用的 outline_system.xml
    # 为简单起见，这里假设 outline_system.xml 存在并专门指导输出 OutlineOutput
    prompt_path = Path(__file__).parents[2] / "prompts" / "structure_system.xml" 
    
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            system_template = f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"致命错误：未找到提示词文件 {prompt_path}")

    # 包装一个新的系统提示，强制它只输出大纲
    outline_system = system_template + "\n\n【注意】：你现在是 Outline Agent。你只需要输出 page_title 和 page_order（必须是包含 id 和 type 字段的对象列表！）。不要输出 components 细节数据！"

    prompt = ChatPromptTemplate.from_messages([
        ("system", outline_system),
        ("human", "用户的最新指令：\n<user_input>\n{{ user_query }}\n</user_input>\n(请以 JSON 格式输出)")
    ], template_format="jinja2")

    try:
        chain = prompt | structured_llm
        
        inputs = {
            "is_update": is_update,
            "current_data_dsl": json.dumps(current_data_dsl, ensure_ascii=False),
            "selected_element": selected_element,
            "active_archetype": active_archetype, 
            "content_context": content_context,
            "assets_text": assets_text,
            "user_query": user_query
        }
        
        result: OutlineOutput = await invoke_with_retry(chain, inputs)
        
        archetype_str = result.detected_archetype.value if hasattr(result.detected_archetype, 'value') else str(result.detected_archetype)
        if archetype_str == "general" and active_archetype != "general":
            archetype_str = active_archetype

        # 转换为字典列表
        page_outline = [{"id": comp.id, "type": comp.type} for comp in result.page_order]
        
        # 初始化 data_dsl 的大纲部分
        dsl_patch = {
            "page_title": result.page_title,
            "page_order": [comp["id"] for comp in page_outline]
        }
        
        print(f"🗺️ [大纲裂变] 生成了 {len(page_outline)} 个组件任务准备并发。")

        return {
            "page_outline": page_outline,
            "data_dsl": dsl_patch, # 先把大纲塞进去
            "active_archetype": archetype_str
        }
                
    except Exception as e:
        print(f"❌ Outline Agent 最终失败: {e}")
        return {"page_outline": []}
