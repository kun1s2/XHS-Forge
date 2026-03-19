import uuid
from typing import Annotated
from langchain_core.tools import tool, InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from langchain_core.messages import ToolMessage

# --- 🛠️ 画布手术刀：大纲 Agent 的 CRUD 工具箱 ---

@tool
def append_block(
    component_type: str, 
    content_brief: str, 
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[dict, InjectedState]
) -> Command:
    """
    【追加积木】：当你需要在页面末尾新增一个组件时，调用此工具。
    - component_type: 组件的类型名称 (如 'CoverSwiper', 'PollBlock', 'VersusCard')。
    - content_brief: 给下游撰稿工兵的指令简报 (如 '提取核心参数，语气要激动')。
    """
    new_id = f"{component_type.lower()}_{uuid.uuid4().hex[:6]}"
    new_block = {
        "id": new_id,
        "component_type": component_type,
        "content_brief": content_brief
    }
    
    current_blocks = state.get("data_dsl", {}).get("blocks", [])
    updated_blocks = list(current_blocks)
    updated_blocks.append(new_block)
    
    return Command(
        update={
            "data_dsl": {"blocks": updated_blocks, "_blocks_override": True},
            "messages": [ToolMessage(content=f"成功追加积木: {new_id}", tool_call_id=tool_call_id)]
        }
    )

@tool
def insert_block(
    component_type: str, 
    content_brief: str, 
    insert_index: int,
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[dict, InjectedState]
) -> Command:
    """
    【插入积木】：当你需要将新组件精确插入到页面的特定位置时，调用此工具。
    - component_type: 组件的类型名称。
    - content_brief: 撰稿指令简报。
    - insert_index: 插入的数组索引 (0 表示插在最前面)。请先通过观测仪表盘确认当前 blocks 的长度！
    """
    new_id = f"{component_type.lower()}_{uuid.uuid4().hex[:6]}"
    new_block = {"id": new_id, "component_type": component_type, "content_brief": content_brief}
    
    current_blocks = state.get("data_dsl", {}).get("blocks", [])
    updated_blocks = list(current_blocks)
    
    safe_index = min(max(0, insert_index), len(updated_blocks))
    updated_blocks.insert(safe_index, new_block)
    
    return Command(
        update={
            "data_dsl": {"blocks": updated_blocks, "_blocks_override": True},
            "messages": [ToolMessage(content=f"成功在索引 {safe_index} 插入积木: {new_id}", tool_call_id=tool_call_id)]
        }
    )

@tool
def remove_block(
    block_id: str, 
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[dict, InjectedState]
) -> Command:
    """
    【删除积木】：当你发现某个组件排版多余，或用户明确要求删除时，调用此工具。
    - block_id: 必须提供你想要删除的积木的精确 ID。
    """
    current_blocks = state.get("data_dsl", {}).get("blocks", [])
    updated_blocks = [b for b in current_blocks if b.get("id") != block_id]
    
    return Command(
        update={
            "data_dsl": {"blocks": updated_blocks, "_blocks_override": True},
            "messages": [ToolMessage(content=f"成功删除积木: {block_id}", tool_call_id=tool_call_id)]
        }
    )

@tool
def update_block_brief(
    block_id: str, 
    new_brief: str, 
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[dict, InjectedState]
) -> Command:
    """
    【更新积木简报】：当你不需要更换组件，只需要调整工兵的撰写要求时，调用此工具。
    - block_id: 要修改的积木 ID。
    - new_brief: 全新的撰写指令。
    """
    current_blocks = state.get("data_dsl", {}).get("blocks", [])
    updated_blocks = []
    
    found = False
    for b in current_blocks:
        new_b = dict(b)
        if new_b.get("id") == block_id:
            new_b["content_brief"] = new_brief
            new_b["needs_rebuild"] = True 
            found = True
        updated_blocks.append(new_b)
            
    msg = f"成功更新积木简报: {block_id}" if found else f"未找到积木: {block_id}"
    return Command(
        update={
            "data_dsl": {"blocks": updated_blocks, "_blocks_override": True},
            "messages": [ToolMessage(content=msg, tool_call_id=tool_call_id)]
        }
    )

@tool
def finish_layout(tool_call_id: Annotated[str, InjectedToolCallId]) -> Command:
    """
    【结束排版】：当你认为画布已经完美，或者已经彻底完成了用户的修改需求时，【必须】调用此工具跳出循环！
    """
    return Command(
        update={
            "messages": [ToolMessage(content="排版总编已完成画布定稿。", tool_call_id=tool_call_id)]
        }
    )
