import json
from typing import Annotated, Dict, Any
from langchain_core.tools import tool, InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from langchain_core.messages import ToolMessage

# --- 🔪 微创手术刀：用于 patch_node 的原子级修改工具 ---

@tool
def apply_diff_update(
    component_id: str, 
    diff_patch: str, 
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[dict, InjectedState]
) -> Command:
    """
    【应用差分更新】：对指定组件的数据进行原子级微调。
    - component_id: 目标积木的 ID (如 'title_1')。
    - diff_patch: 一个 JSON 字符串，包含需要修改的字段。
      例如：'{"title": "更炸裂的新标题", "style": {"css_classes": "text-red-500"}}'。
      未包含在 patch 中的字段将保持原样，不受影响。
    """
    try:
        patch_dict = json.loads(diff_patch)
    except json.JSONDecodeError:
        return Command(
            update={"messages": [ToolMessage(content=f"❌ JSON 解析失败: {diff_patch}", tool_call_id=tool_call_id)]}
        )

    # 获取当前完整状态
    data_dsl = state.get("data_dsl", {})
    style_dsl = state.get("style_dsl", {})
    
    # 提取目标组件数据
    target_data = data_dsl.get(component_id, {})
    target_style = style_dsl.get(component_id, {})
    
    # 分离数据与样式更新
    data_update = {k: v for k, v in patch_dict.items() if k != "style"}
    style_update = patch_dict.get("style", {})
    
    # 执行原子级合并（Shallow Merge）
    # 注意：对于嵌套结构（如 style），这里做简单的单层合并
    new_data = {**target_data, **data_update}
    new_style = {**target_style, **style_update}
    
    # 构造原子更新指令
    # 我们利用 _block_update 机制（需要在 state.py 中确认是否支持深度合并，这里先用直接覆盖 key 的方式）
    return Command(
        update={
            "data_dsl": {component_id: new_data},
            "style_dsl": {component_id: new_style},
            "messages": [ToolMessage(content=f"✅ 已对 {component_id} 执行微创手术。更新字段: {list(patch_dict.keys())}", tool_call_id=tool_call_id)]
        }
    )

@tool
def inspect_component_state(
    component_id: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[dict, InjectedState]
) -> Command:
    """
    【诊断内窥镜】：在动刀前，先查看该组件当前的完整数据和样式状态。
    """
    data_dsl = state.get("data_dsl", {})
    comp_data = data_dsl.get(component_id, "未找到该组件数据")
    
    return Command(
        update={
            "messages": [ToolMessage(content=f"🔍 组件 {component_id} 当前状态:\n{json.dumps(comp_data, ensure_ascii=False, indent=2)}", tool_call_id=tool_call_id)]
        }
    )
