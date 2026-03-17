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
        # 🧠 哨兵三轨制：策划大脑切换为最强的 BRAIN 模型
        _llm_instance = create_llm(
            model=settings.LLM_BRAIN_MODEL, 
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

    # ✨ 【审美多样性爆发】：赋予大纲大脑“艺术策展人”人格
    outline_system = f"""你是一个顶级的 Generative UI 视觉策展人。你的任务是将内容转化为一棵极具审美冲击力的 AST 树。

    【审美进阶法则 (最高优先级)】:
    1. 非对称 Bento 布局：你可以在 BentoGrid 的 props 中定义 `layout_vibe: "organic"`。此时，你可以大胆使用奇数跨列（如 col_span: 1 与 col_span: 2 混搭），制造视觉上的跳跃感。
    2. 视觉权重分配：你必须为每一个子组件在 props 中标注 `visual_priority` ("high", "medium", "low")。
    - high: 对应核心卖点卡片或情绪引言，将获得更强的阴影和动效。
    - low: 对应次要参数或辅助文案，将获得更轻的视觉分量。
    3. 材质嗅探：根据文案情绪，在 root 节点的 props 中建议一种材质（variant）。
    - 科技测评 -> neon / flat-dark
    - 生活种草 -> claymorphism / glassmorphism
    - 文艺复古 -> paper-cut / asymmetric corner_style

    【输出规范】:
    - 必须包含 page_title, page_theme。
    - root 节点必须包含整体的视觉旋钮配置。
    - 每个组件必须有合理的 visual_priority。

    【当前业务原型】: {active_archetype}
    """

    prompt = ChatPromptTemplate.from_messages([
        ("system", outline_system),
        ("human", "请基于以下生成的文案，策划一场“审美爆发”的 UI 视觉盛宴：\n<content>\n{{ content_context }}\n</content>\n(请通过调用工具输出 JSON 格式结果)")
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

        # 获取根节点的 AST 字典表示
        ast_root = result.root.model_dump(exclude_none=True)
        
        # 初始化 data_dsl 的大纲部分
        dsl_patch = {
            "page_title": result.page_title,
            "page_theme": result.page_theme,
            "root": ast_root
        }
        
        print(f"🗺️ [大纲裂变] AST 树生成完毕，根节点 ID: {result.root.id}")

        return {
            "page_outline": ast_root,
            "data_dsl": dsl_patch, # 先把大纲塞进去
            "active_archetype": archetype_str
        }
                
    except Exception as e:
        print(f"❌ Outline Agent 最终失败: {e}")
        if settings.DEBUG_MODE:
            raise e
        return {"page_outline": {}}
