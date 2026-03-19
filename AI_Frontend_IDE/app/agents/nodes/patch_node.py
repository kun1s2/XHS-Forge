import json
from langgraph.prebuilt import create_react_agent
from app.core.llm_factory import create_llm
from app.agents.state import UIProjectState
from app.core.config import settings
from app.agents.tools_registry import PATCH_TOOLS
from langchain_core.messages import HumanMessage, AIMessage

async def surgical_patch_agent(state: UIProjectState) -> dict:
    """
    【手术刀 Agent 7.0】：ReAct 驱动的原子级组件微调专家。
    流程：诊断 (inspect) -> 搜证 (google_images, 可选) -> 开刀 (apply_diff)。
    """
    target_id = state.get("selected_element_id")
    if not target_id:
        return {"main_messages": [AIMessage(content="⚠️ 未选中任何组件，无法执行手术。")]}

    main_msgs = state.get("main_messages", [])
    user_instruction = str(main_msgs[-1].content) if main_msgs else "优化内容"

    print(f"🔪 [手术刀] 正在对组件 {target_id} 进行微创修复...")

    llm = create_llm(
        model=settings.LLM_LOGIC_MODEL,
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        temperature=0.2 # 微调需要高确定性
    )

    # 构建微创医生
    patch_doctor = create_react_agent(
        model=llm,
        tools=PATCH_TOOLS,
        prompt=f"""你是一个资深的前端微调专家。
当前目标组件 ID: {target_id}。
用户修改指令: {user_instruction}。

【你的手术流程】：
1. 诊断：调用 inspect_component_state 查看组件当前的 JSON 数据。
2. 决策：根据用户指令判断需要修改哪些字段（如 title, paragraphs, image_url）。
   - 如果用户想换图但没给图，你可以调用 google_images 搜一张，然后填入 image_url。
3. 开刀：调用 apply_diff_update 传入 JSON 补丁。
   - 补丁格式示例: '{{"title": "新标题", "style": {{"css_classes": "bg-red-500"}}}}'
4. 结束：修改完成后停止调用工具。
"""
    )

    try:
        # 为了让工具能访问到 state，我们需要把 state 传进去
        # create_react_agent 会自动处理 messages，我们只需要把 state 作为上下文注入
        # 注意：langgraph 0.2 的 create_react_agent 默认 behavior 是将输入作为初始 state
        # 我们这里构造一个临时的 input state
        
        inputs = {
            "messages": [("user", f"请对组件 {target_id} 执行修改：{user_instruction}")],
            # 注入全局状态以供工具读取 (InjectedState)
            "data_dsl": state.get("data_dsl"),
            "style_dsl": state.get("style_dsl")
        }
        
        # 执行循环
        result = await patch_doctor.ainvoke(inputs)
        
        # 提取工具产生的副作用 (data_dsl/style_dsl 的更新已经通过 Command 在工具里完成了)
        # 我们只需要提取最后一条回复反馈给用户
        last_msg = result["messages"][-1]
        content = getattr(last_msg, "content", "修改已完成")
        
        return {
            "main_messages": [AIMessage(content=f"✨ {content}")]
        }

    except Exception as e:
        print(f"❌ [手术失败]: {e}")
        return {"main_messages": [AIMessage(content="🔧 手术遭遇未知错误，请重试。")]}
