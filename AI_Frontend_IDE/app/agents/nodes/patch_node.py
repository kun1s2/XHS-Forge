"""Minimal patch agent for selected blocks.

The patch tools still operate on execution payloads, but this node sources
those payloads from the canonical NoteDocument bridge instead of direct state
shape coupling.
"""

from app.core.agent_runtime import create_controlled_agent
from app.core.llm_factory import create_llm
from app.agents.state import UIProjectState
from app.core.config import settings
from app.agents.tools_registry import PATCH_TOOLS
from app.core.note_document import build_note_document_from_state
from langchain_core.messages import AIMessage

async def surgical_patch_agent(state: UIProjectState) -> dict:
    """
    【手术刀 Agent 7.0】：ReAct 驱动的原子级组件微调专家。
    流程：诊断 (inspect) -> 搜证 (google_images, 可选) -> 开刀 (apply_diff)。
    """
    target_id = state.get("selected_element_id")
    if not target_id:
        return {
            "main_messages": [AIMessage(content="⚠️ 未选中任何组件，无法执行手术。")],
            "agent_backends": {"patch_doctor": "skipped_no_selection"},
        }

    main_msgs = state.get("main_messages", [])
    user_instruction = str(main_msgs[-1].content) if main_msgs else "优化内容"

    print(f"🔪 [手术刀] 正在对组件 {target_id} 进行微创修复...")
    note_document = build_note_document_from_state(state)

    llm = create_llm(
        model=settings.LLM_LOGIC_MODEL,
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        temperature=0.2 # 微调需要高确定性
    )

    system_prompt = """你是一个资深的前端微调专家。
你的职责是围绕当前选中组件执行最小必要修改，而不是重写整页。

【你的手术流程】
1. 诊断：调用 inspect_component_state 查看组件当前 JSON 数据。
2. 决策：根据用户指令判断需要修改哪些字段（如 title、paragraphs、image_url）。
3. 换图：如果用户想换图但没给图，可以调用 google_images 搜图，再把结果填入 image_url。
4. 开刀：调用 apply_diff_update 传入 JSON 补丁。
   - 补丁格式示例: '{"title": "新标题", "style": {"css_classes": "bg-red-500"}}'
5. 结束：修改完成后立即停止调用工具。

【约束】
- 只修改必要字段。
- 不要输出 JSON 到最终回复。
- 完成后用一句中文确认修改完成。"""

    # 构建微创医生
    patch_doctor = create_controlled_agent(
        model=llm,
        tools=PATCH_TOOLS,
        name="patch_doctor",
        prompt=system_prompt,
    )

    try:
        inputs = {
            "messages": [("user", f"当前目标组件 ID: {target_id}。用户修改指令: {user_instruction}")],
            "note_document": note_document,
        }
        
        # 执行循环
        result = await patch_doctor.ainvoke(inputs)
        
        # 提取工具产生的副作用（文档状态更新已经通过 Command 在工具里完成了）
        # 我们只需要提取最后一条回复反馈给用户
        last_msg = result["messages"][-1]
        content = getattr(last_msg, "content", "修改已完成")
        
        # 把子图里被工具修改过的执行补丁回传给全局总线。
        return {
            **({"note_document": result["note_document"]} if result.get("note_document") else {}),
            "main_messages": [AIMessage(content=f"✨ {content}")],
            "agent_backends": {"patch_doctor": patch_doctor.backend},
        }

    except Exception as e:
        print(f"❌ [手术失败]: {e}")
        return {
            "main_messages": [AIMessage(content="🔧 手术遭遇未知错误，请重试。")],
            "agent_backends": {"patch_doctor": patch_doctor.backend},
        }
